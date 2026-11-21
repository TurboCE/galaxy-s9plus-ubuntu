#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Private GNSS start-position assistance; no coordinates or cell IDs on stdout."""
import argparse, datetime, json, math, os, socket, stat, subprocess, tempfile, time
from pathlib import Path
from urllib import request, error
ROOT=Path('/var/lib/g965n-gnss-seed')

def allowed():
    r=subprocess.run(['runuser','-u','ubuntu','--','env','XDG_RUNTIME_DIR=/run/user/1000',
        'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus','gsettings','get',
        'org.gnome.system.location','enabled'],capture_output=True,text=True,timeout=3)
    return r.returncode==0 and r.stdout.strip()=='true'

def validate(r, now, aged=True):
    if not isinstance(r,dict) or r.get('source') not in ('network','gnss'):return None
    for key in ('lat','lon','accuracy','time'):
        if type(r.get(key)) not in (float,int) or not math.isfinite(r[key]):return None
    age=now-r['time']
    if not(-90<=r['lat']<=90 and -180<=r['lon']<=180 and 1<=r['accuracy']<=100000 and 0<=age<=300):return None
    result=dict(r)
    result['sample_accuracy']=r['accuracy']
    # Conservative travel allowance, never pretend old/coarse data is precise.
    result['accuracy']=r['accuracy']+(350*age if aged else 0)
    return result if result['accuracy']<=100000 else None

def save(r):
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    info=ROOT.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077:raise ValueError('Private cache required')
    destination=ROOT/(r['source']+'.json')
    with tempfile.NamedTemporaryFile(mode='w',dir=ROOT,delete=False) as f:
        tmp=Path(f.name)
        try:
            os.chmod(tmp,0o600);json.dump(r,f);f.flush();os.fsync(f.fileno());os.replace(tmp,destination)
        finally:tmp.unlink(missing_ok=True)

def cached():
    results=[]
    try:
        info=ROOT.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077:return None
    except OSError:return None
    for name in ('gnss','network'):
        p=ROOT/(name+'.json')
        try:
            info=p.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode&0o077 or info.st_size>4096:continue
            r=validate(json.loads(p.read_text()),time.time())
            if r:results.append(r)
        except (OSError,ValueError):pass
    return min(results,key=lambda r:r['accuracy']) if results else None

def lookup(cell_only=False):
    from gi.repository import Gio
    bus=Gio.bus_get_sync(Gio.BusType.SYSTEM,None);dest='org.freedesktop.ModemManager1'
    cells=[]
    try:
        objs=bus.call_sync(dest,'/org/freedesktop/ModemManager1','org.freedesktop.DBus.ObjectManager',
            'GetManagedObjects',None,None,0,2000,None).unpack()[0]
        path=next(p for p,v in objs.items() if dest+'.Modem' in v)
        rows=bus.call_sync(dest,path,dest+'.Modem','GetCellInfo',None,None,0,2500,None).unpack()[0]
        for row in rows[:32]:
            code=row.get('operator-id','')
            if len(code) not in (5,6) or not code.isdigit():continue
            if not all(k in row for k in ('tac','ci')):continue
            cells.append({'radioType':'lte','mobileCountryCode':int(code[:3]),
                'mobileNetworkCode':int(code[3:]),'locationAreaCode':int(row['tac'],16),'cellId':int(row['ci'],16)})
    except Exception:pass
    if cell_only and not cells:return None,'no-cells'
    payload={'cellTowers':cells,'considerIp':not cell_only,'fallbacks':{'ipf':not cell_only,'lacf':not cell_only}}
    req=request.Request('https://api.beacondb.net/v1/geolocate',data=json.dumps(payload).encode(),
        headers={'Content-Type':'application/json','User-Agent':'G965N-Ubuntu-GNSS-assistance/1.0'})
    try:
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):raise error.URLError('redirect-disabled')
        with request.build_opener(NoRedirect).open(req,timeout=3) as response:
            raw=response.read(16385)
            if len(raw)>16384:return None,'oversized'
        value=json.loads(raw);loc=value['location']
        r={'source':'network','lat':loc['lat'],'lon':loc['lng'],'accuracy':value['accuracy'],'time':time.time()}
        return (r,'ok') if validate(r,time.time(),False) else (None,'invalid')
    except error.HTTPError as e:return None,'http-'+str(e.code)
    except Exception:return None,'unavailable'

def prepare():
    if not allowed():return None
    r=cached()
    if r:return r
    r,status=lookup()
    if r:save(r)
    return r

def gps_fix(record, now):
    if record.get('class')!='TPV' or record.get('mode') not in (2,3):return None
    try:
        dt=datetime.datetime.fromisoformat(record['time'].replace('Z','+00:00'))
        if dt.tzinfo is None:return None
        stamp=dt.timestamp()
        if not 0<=now-stamp<=10:return None
        accuracy=math.hypot(record.get('epx',float('nan')),record.get('epy',float('nan')))
        r={'source':'gnss','lat':record['lat'],'lon':record['lon'],'accuracy':accuracy,'time':stamp}
        return r if validate(r,now,False) else None
    except (KeyError,ValueError,TypeError):return None

def watch():
    last=0
    while True:
        try:
            with socket.create_connection(('127.0.0.1',2948),timeout=5) as sock:
                sock.sendall(b'?WATCH={"enable":true,"json":true};\n');sock.settimeout(5);buf=b''
                while True:
                    try:data=sock.recv(65536)
                    except socket.timeout:continue
                    if not data:break
                    buf+=data
                    if len(buf)>262144:break
                    while b'\n' in buf:
                        line,buf=buf.split(b'\n',1)
                        try:r=gps_fix(json.loads(line),time.time())
                        except (ValueError,AttributeError):continue
                        if r and time.monotonic()-last>=10 and allowed():
                            save(r);last=time.monotonic()
        except OSError:pass
        time.sleep(5)

if __name__=='__main__':
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');p.add_argument('--cell-only',action='store_true');a=p.parse_args()
    if a.watch:watch()
    elif a.cell_only:
        r,status=lookup(True) if allowed() else (None,'location-disabled')
        print(json.dumps({'cell_only_lookup':status,'accuracy_m':r['accuracy'] if r else None}))
    else:
        r=prepare();print(json.dumps({'seed_available':bool(r),'source':r['source'] if r else None,'accuracy_m':round(r['accuracy']) if r else None}))

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded live GPSD counters; never print/store positions or satellite IDs."""
import argparse,json,socket,time,atexit
from gi.repository import Gio,GLib
p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=180);a=p.parse_args()
if not 10<=a.seconds<=300:p.error('10..300 seconds required')
# Request GPS through the same desktop permission path as the viewer. A GPSD
# observer alone does not keep the receiver on after the last app exits.
bus=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
service='org.freedesktop.GeoClue2';manager='/org/freedesktop/GeoClue2/Manager'
def call(path,iface,method,args=None):
 return bus.call_sync(service,path,iface,method,args,None,0,10000,None)
client=call(manager,service+'.Manager','GetClient').unpack()[0]
def cleanup():
 try:call(client,service+'.Client','Stop')
 finally:call(manager,service+'.Manager','DeleteClient',GLib.Variant('(o)',(client,)))
atexit.register(cleanup)
for key,value in [('DesktopId',GLib.Variant('s','g965n-xgps')),('RequestedAccuracyLevel',GLib.Variant('u',8))]:
 call(client,'org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',(service+'.Client',key,value)))
call(client,service+'.Client','Start')
types={};gsv_visible=cn0=0
counts={};visible=used=0;modes=set();start=time.monotonic();buf=b''
with socket.create_connection(('127.0.0.1',2948),timeout=5) as s:
 s.sendall(b'?WATCH={"enable":true,"json":true,"raw":1};\n');s.settimeout(2)
 while time.monotonic()-start<a.seconds:
  try:data=s.recv(65536)
  except socket.timeout:continue
  if not data:raise RuntimeError('GPSD disconnected')
  buf+=data
  if len(buf)>262144:raise RuntimeError('Oversized GPSD record')
  while b'\n' in buf:
   ln,buf=buf.split(b'\n',1)
   if ln.startswith(b'$'):
    c='NMEA'
    fields=ln.split(b'*',1)[0].split(b',')
    if len(fields[0])==6:
     kind=fields[0][3:].decode('ascii','replace');types[kind]=types.get(kind,0)+1
     if kind=='GSV' and len(fields)>=4:
      try:gsv_visible=max(gsv_visible,int(fields[3]))
      except ValueError:pass
      for v in fields[7::4]:
       try:
        n=int(v)
        if 0<=n<=99:cn0=max(cn0,n)
       except ValueError:pass
   else:
    try:r=json.loads(ln)
    except (ValueError,UnicodeError):continue
    c=r.get('class','unknown')
    if c=='SKY':
     sats=r.get('satellites',[]);visible=max(visible,len(sats));used=max(used,sum(bool(x.get('used')) for x in sats))
    if c=='TPV' and type(r.get('mode')) is int:modes.add(r['mode'])
   counts[c]=counts.get(c,0)+1
print(json.dumps({'seconds':round(time.monotonic()-start),'records':counts,'visible_max':visible,'used_max':used,'nmea_types':types,'gsv_visible_max':gsv_visible,'cn0_max':cn0,'modes':sorted(modes),'fix':bool(modes & {2,3})}))

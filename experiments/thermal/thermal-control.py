#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded calibrated-battery cooling overlay. Never changes voltage/charger policy."""
import argparse,hashlib,importlib.util,json,os,signal,socket,stat,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path('/usr/local/lib/g965n-thermal-qos')
STATE=Path('/var/lib/g965n-thermal-qos')
LEVEL=Path('/sys/module/g965n_thermal_qos/parameters/level')
STOP=False
RATE=Path('/sys/devices/system/cpu/cpufreq/schedutil/rate_limit_us')
CLOCK=getattr(time,'CLOCK_BOOTTIME',time.CLOCK_MONOTONIC)

def decision(row,now,was_hot):
    stamp=row.get('end_monotonic_ns')
    if type(stamp) is not int or not 0<=now-stamp<35_000_000_000:return True,'stale_measurement'
    try:
        values=[row['temperature'][n]['temperature_deci_c'] for n in ('battery','usb','charger')]
        if row.get('temperature_error') or any(type(v) is not int or not -200<=v<=900 for v in values):raise ValueError()
    except (KeyError,ValueError,TypeError):return True,'invalid_temperature'
    # Reduce load before the independent 41C charging stop.
    hot=values[0]>360 if was_hot else values[0]>=380
    # A USB/charger hot spot is also a reason to retain the cooling overlay.
    if values[1]>=500 or values[2]>=600:hot=True
    return hot,'thermal_cooling' if hot else 'normal'

def cadence_request(rate,current,hot):
    rate=dict(rate)
    if rate['last'] is not None and current!=rate['last']:
        rate['original']=current
    cadence=max(200000,rate['original']) if hot else rate['original']
    rate['last']=cadence
    return rate,cadence

def panel_is_off(drm=Path('/sys/class/drm')):
    """Only the unique internal DSI connector; missing/ambiguous is unknown."""
    panels=list(drm.glob('card*-DSI-*'))
    if len(panels)!=1:return None
    try:
        enabled=(panels[0]/'enabled').read_text().strip()
        dpms=(panels[0]/'dpms').read_text().strip()
    except OSError:return None
    if enabled=='disabled' and dpms=='Off':return True
    if enabled=='enabled' and dpms=='On':return False
    return None

def cooling_request(thermal_hot,thermal_reason,panel_off):
    if thermal_hot:return True,thermal_reason
    if panel_off is True:return True,'screen_off_idle'
    if panel_off is None:return True,'unknown_display_state'
    return False,'normal'

def latest_completed_sample(path=Path('/var/lib/g965n-charge-observer/samples.jsonl')):
    # A concurrent writer may have appended only part of the newest record.
    # The previous complete record must still satisfy decision()'s age limit.
    with path.open('rb') as f:
        f.seek(0,2);f.seek(max(0,f.tell()-131072));lines=f.read().splitlines()
    for line in reversed(lines):
        try:row=json.loads(line)
        except ValueError:continue
        if isinstance(row,dict) and 'end_monotonic_ns' in row:return row
    raise ValueError('No completed sample')

def restored_hot(state,boot):
    # Keep a cleared hysteresis latch across same-boot service restarts.
    # New/unknown boot or invalid state starts conservatively.
    if state.get('boot')==boot and type(state.get('thermal_hot')) is bool:
        return state['thermal_hot']
    return True

def notify(message):
    address=os.environ.get('NOTIFY_SOCKET')
    if not address:return
    if address.startswith('@'):address='\0'+address[1:]
    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:
        sock.sendto(message.encode(),address)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-backed-up-cooling',action='store_true',required=True)
    p.add_argument('--fail-closed',action='store_true')
    a=p.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Root required')
    spec=importlib.util.spec_from_file_location('g','/usr/local/lib/g965n-led-trial/led-control.py')
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.preflight()
    for f in (ROOT/'pins.json',ROOT/'g965n-thermal-qos.ko',Path(__file__)):
        s=f.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid or s.st_mode&0o077:raise RuntimeError('Private root-owned files required')
    module=ROOT/'g965n-thermal-qos.ko';sha=hashlib.sha256(module.read_bytes()).hexdigest()
    if json.loads((ROOT/'pins.json').read_text())!={module.name:sha}:raise RuntimeError('Module pin mismatch')
    if subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).strip()!=os.uname().release+' SMP preempt mod_unload aarch64':raise RuntimeError('ABI mismatch')
    os.umask(0o077);STATE.mkdir(mode=0o700,exist_ok=True)
    for d in (ROOT,STATE):
        info=d.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid or info.st_mode&0o077:raise RuntimeError('Private root-owned directories required')
    receipt=STATE/'loaded.json';boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    expected={'boot':boot,'module_sha256':sha}
    if LEVEL.exists():
        if json.loads(receipt.read_text())!=expected:raise RuntimeError('Unowned loaded module preserved')
    else:
        subprocess.run(['insmod',str(module),'enable_g965n=1','level=1'],check=True)
        try:receipt.write_text(json.dumps(expected))
        except Exception:
            subprocess.run(['rmmod','g965n_thermal_qos'],check=True);raise
    if a.fail_closed:
        LEVEL.write_text('1\n')
        if LEVEL.read_text().strip()!='1':raise RuntimeError('Cooling fallback readback failed')
        print('Owned conservative CPU/GPU caps retained',flush=True)
        return
    def stop(*_):
        global STOP
        STOP=True
    for s in (signal.SIGTERM,signal.SIGINT):signal.signal(s,stop)
    # Retain the pre-trial governor cadence across service restarts, only
    # when this boot's guarded receipt owns it. Do not overwrite later changes.
    rate_state=STATE/'rate-owned.json'
    if rate_state.exists():
        rate=json.loads(rate_state.read_text())
        if rate.get('boot')!=boot:rate={'boot':boot,'original':int(RATE.read_text()),'last':None}
    else:rate={'boot':boot,'original':int(RATE.read_text()),'last':None}
    try:hot=restored_hot(json.loads((STATE/'state.json').read_text()),boot)
    except (OSError,ValueError,TypeError,AttributeError):hot=True
    previous=None;ready=False
    try:
        while not STOP:
            try:
                row=latest_completed_sample();hot,reason=decision(row,time.clock_gettime_ns(CLOCK),hot)
            except (OSError,ValueError,IndexError):hot=True;reason='missing_measurement'
            panel_off=panel_is_off()
            cooling,reason=cooling_request(hot,reason,panel_off)
            current=int(RATE.read_text())
            rate,cadence=cadence_request(rate,current,cooling)
            if current!=cadence:RATE.write_text(str(cadence)+'\n')
            rate_state.write_text(json.dumps(rate))
            value='1' if cooling else '0'
            if LEVEL.read_text().strip()!=value:LEVEL.write_text(value+'\n')
            state={'boot':boot,'cooling':cooling,'thermal_hot':hot,'panel_off':panel_off,'reason':reason,
                   'utc':datetime.now(timezone.utc).isoformat()}
            tmp=STATE/'state.tmp';tmp.write_text(json.dumps(state));tmp.replace(STATE/'state.json')
            changed=(cooling,hot,panel_off,reason)
            if changed!=previous:
                print(json.dumps({k:v for k,v in state.items() if k!='boot'}),flush=True)
                previous=changed
            if not ready:
                notify('READY=1');ready=True
            notify('WATCHDOG=1')
            for _ in range(25):
                if STOP:break
                time.sleep(.2)
    finally:
        # A stopped/failed temperature supervisor must not silently release cooling.
        LEVEL.write_text('1\n')

if __name__=='__main__':main()

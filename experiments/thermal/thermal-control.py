#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded calibrated-battery cooling overlay. Never changes voltage/charger policy."""
import argparse,hashlib,importlib.util,json,os,signal,stat,subprocess,time
from pathlib import Path
ROOT=Path('/usr/local/lib/g965n-thermal-qos')
STATE=Path('/var/lib/g965n-thermal-qos')
LEVEL=Path('/sys/module/g965n_thermal_qos/parameters/level')
STOP=False
RATE=Path('/sys/devices/system/cpu/cpufreq/schedutil/rate_limit_us')
CLOCK=getattr(time,'CLOCK_BOOTTIME',time.CLOCK_MONOTONIC)

def decision(row,now,was_hot):
    if not 0<=now-row.get('end_monotonic_ns',-100_000_000_000)<35_000_000_000:return True,'stale_measurement'
    try:
        values=[row['temperature'][n]['temperature_deci_c'] for n in ('battery','usb','charger')]
        if row.get('temperature_error') or any(type(v) is not int or not -200<=v<=900 for v in values):raise ValueError()
    except (KeyError,ValueError,TypeError):return True,'invalid_temperature'
    hot=values[0]>390 if was_hot else values[0]>=410
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

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-backed-up-cooling',action='store_true',required=True)
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
    hot=True
    try:
        while not STOP:
            try:
                # Avoid whole-file reads as the rotated recorder grows.
                with open('/var/lib/g965n-charge-observer/samples.jsonl','rb') as f:
                    f.seek(0,2);f.seek(max(0,f.tell()-131072));lines=f.read().splitlines()
                row=json.loads(lines[-1]);hot,reason=decision(row,time.clock_gettime_ns(CLOCK),hot)
            except (OSError,ValueError,IndexError):hot=True;reason='missing_measurement'
            current=int(RATE.read_text())
            rate,cadence=cadence_request(rate,current,hot)
            if current!=cadence:RATE.write_text(str(cadence)+'\n')
            rate_state.write_text(json.dumps(rate))
            value='1' if hot else '0'
            if LEVEL.read_text().strip()!=value:LEVEL.write_text(value+'\n')
            tmp=STATE/'state.tmp';tmp.write_text(json.dumps({'cooling':hot,'reason':reason}));tmp.replace(STATE/'state.json')
            for _ in range(25):
                if STOP:break
                time.sleep(.2)
    finally:
        # A stopped/failed temperature supervisor must not silently release cooling.
        LEVEL.write_text('1\n')

if __name__=='__main__':main()

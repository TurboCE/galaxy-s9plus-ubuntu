#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded read-only qualification of hot-stop -> cool -> screen-off charging.

A pass means only a short observed recovery window, never full thermal parity.
Raw reports stay root-private on the device. No hardware or policy writes.
"""
import argparse,json,os,signal,tempfile,time
from pathlib import Path
CLOCK=getattr(time,'CLOCK_BOOTTIME',time.CLOCK_MONOTONIC)
STOP=False

def now():return time.clock_gettime(CLOCK)

def latest():
    with open('/var/lib/g965n-charge-observer/samples.jsonl','rb') as f:
        f.seek(0,2);f.seek(max(0,f.tell()-131072));lines=f.read().splitlines()
    for line in reversed(lines):
        try:r=json.loads(line)
        except ValueError:continue
        if 'end_monotonic_ns' in r:return r
    raise ValueError('No completed sample')

def observe_phases(phases,temp,enabled,fresh,reasons):
    hot,cold,recovered=phases
    if not fresh:return phases
    hot=hot or (enabled==0 and (temp>=410 or 'swelling_temperature_stop' in reasons))
    cold=cold or (hot and temp<=390)
    # The controller can turn CHG on between two recorder samples.
    recovered=recovered or (cold and temp<410 and enabled==1)
    return hot,cold,recovered

def contiguous(previous,current):
    return previous is None or (type(current) is int and 0<current-previous<=35_000_000_000)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-read-only-recovery',action='store_true',required=True)
    p.add_argument('--seconds',type=int,default=1200);a=p.parse_args()
    if os.geteuid()!=0 or not 120<=a.seconds<=1800:raise RuntimeError('Root and bounded duration required')
    import importlib.util
    s=importlib.util.spec_from_file_location('g','/usr/local/lib/g965n-led-trial/led-control.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g);g.preflight()
    os.umask(0o077);root=Path('/var/lib/g965n-thermal-qos');out=Path(tempfile.mkdtemp(prefix='recovery-',dir=root));(root/'latest-recovery-path').write_text(str(out))
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();start=now();seen=None;since=None;count=0;hot_seen=False;cold_seen=False;recovered=False
    def stop(*_):
        global STOP
        STOP=True
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    result={'status':'running','samples':0,'hot_seen':False,'recovered':False}
    while not STOP and now()-start<a.seconds:
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=boot:result.update(status='interrupted',reason='boot_changed');break
        try:
            r=latest();stamp=r['end_monotonic_ns']
            if stamp==seen:
                if now()-stamp/1e9>=35:since=None
                time.sleep(2);continue
            if not contiguous(seen,stamp):since=None
            seen=stamp;count+=1
            guard=json.loads(Path('/var/lib/g965n-charge-guardian/state.json').read_text());cool=json.loads((root/'state.json').read_text())
            battery=r['power_supply']['max170xx_battery'];temp=r['temperature']['battery']['temperature_deci_c'];decoded=r['decoded']
            fresh=0<=now()-stamp/1e9<35 and not r.get('temperature_error')
            hot_seen,cold_seen,recovered=observe_phases((hot_seen,cold_seen,recovered),temp,
                decoded['charge_enabled'],fresh,guard.get('reasons',[]))
            bad=guard.get('hardware_fault') or guard.get('configuration_fault') or bool(r.get('source_initialization_mismatch'))
            limits=[int(Path('/sys/devices/system/cpu/cpufreq/'+n+'/scaling_max_freq').read_text()) for n in ('policy0','policy4')]
            limits.append(int(Path('/sys/class/devfreq/17500000.gpu/max_freq').read_text())//1000)
            acceptable=(fresh and recovered and temp<410 and decoded['charge_enabled']==1 and decoded['input']==3
                and int(battery['current_avg'])>0 and not guard.get('reasons') and cool.get('panel_off') is True
                and cool.get('thermal_hot') is False and cool.get('cooling') is True
                and cool.get('reason')=='screen_off_idle' and all(0<x<=y for x,y in zip(limits,(650000,1066000,260000))))
            since=now() if acceptable and since is None else since if acceptable else None
            result.update(elapsed_seconds=round(now()-start,1),samples=count,hot_seen=hot_seen,cold_seen=cold_seen,recovered=recovered,
                battery_deci_c=temp,current_average_ua=int(battery['current_avg']),capacity=int(battery['capacity']),
                charge_enabled=decoded['charge_enabled'],guardian_reasons=guard.get('reasons'),cooling_reason=cool.get('reason'),
                recovery_window_seconds=round(now()-since,1) if since is not None else 0)
            if bad:result.update(status='failed',reason='hardware_or_configuration_fault')
            elif since is not None and now()-since>=120:result.update(status='passed',reason='observed_120s_screen_off_charging_recovery')
        except (OSError,ValueError,KeyError,TypeError) as e:
            since=None;result.update(reason='unreadable_or_invalid_sample',error=type(e).__name__)
        tempout=out/'result.tmp';tempout.write_text(json.dumps(result,indent=2)+'\n');tempout.replace(out/'result.json')
        if result['status']!='running':break
        time.sleep(5)
    if result['status']=='running':result.update(status='interrupted' if STOP else 'pending',reason='recovery_window_not_completed')
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
    if result['status']=='failed':raise SystemExit(1)

if __name__=='__main__':main()

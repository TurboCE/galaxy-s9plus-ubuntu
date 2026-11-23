#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded safety monitor for one explicitly selected experimental workload.

Stops only the same systemd service invocation on unsafe voltage/temperature
or lost supervision. Never changes charge limits, clocks, profiles or accounts.
"""
import argparse,importlib.util,json,os,re,signal,subprocess,tempfile,time
from pathlib import Path
STOP=False
CLOCK=getattr(time,'CLOCK_BOOTTIME',time.CLOCK_MONOTONIC)

def trip_reason(row,now,voltage,stop_temperature=420):
    try:
        if not 0<=now-row['end_monotonic_ns']<35_000_000_000:return 'stale_temperature'
        if row.get('temperature_error'):return 'invalid_temperature'
        t=row['temperature']['battery']['temperature_deci_c']
        if type(t) is not int or not -200<=t<=900:return 'invalid_temperature'
        if t>=stop_temperature:return 'battery_temperature'
        if voltage<3550000:return 'battery_voltage'
    except (KeyError,TypeError):return 'missing_measurement'
    return None

def identity(unit):
    answer=subprocess.check_output(['systemctl','show',unit,'--property=MainPID','--property=InvocationID'],text=True)
    values=dict(x.split('=',1) for x in answer.splitlines() if '=' in x)
    pid=int(values.get('MainPID','0'))
    if pid<=1:return None
    try:start=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[19]
    except OSError:return None
    return (pid,start,values.get('InvocationID'))

def latest(path):
    with path.open('rb') as f:
        f.seek(0,2);f.seek(max(0,f.tell()-131072));lines=f.read().splitlines()
    for line in reversed(lines):
        try:r=json.loads(line)
        except ValueError:continue
        if isinstance(r,dict) and 'end_monotonic_ns' in r:return r
    return {}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-owned-workload-protection',required=True,action='store_true')
    p.add_argument('--unit',required=True)
    p.add_argument('--seconds',type=int,default=3600)
    p.add_argument('--battery-stop-deci-c',type=int,default=420)
    a=p.parse_args()
    if not re.fullmatch(r'g965n-[a-z0-9-]+\.service',a.unit):p.error('Explicit G965N experimental workload service required')
    if not 30<=a.seconds<=86400 or not 350<=a.battery_stop_deci_c<=430:p.error('Bounded qualification range required')
    if os.geteuid()!=0:raise RuntimeError('Root required')
    s=importlib.util.spec_from_file_location('g','/usr/local/lib/g965n-led-trial/led-control.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g);g.preflight()
    owned=identity(a.unit)
    if owned is None:raise RuntimeError('Selected workload is not running')
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,lambda *_:globals().__setitem__('STOP',True))
    os.umask(0o077);root=Path('/var/lib/g965n-thermal-qos');report=Path(tempfile.mkdtemp(prefix='workload-guard-',dir=root))
    result={'status':'running','unit':a.unit,'battery_stop_deci_c':a.battery_stop_deci_c};start=time.clock_gettime(CLOCK)
    def save():
        with tempfile.NamedTemporaryFile(mode='w',dir=report,delete=False) as f:
            json.dump(result,f);f.flush();os.fsync(f.fileno());tmp=Path(f.name)
        tmp.replace(report/'result.json')
    # Publish a complete initial report before readers can discover its path.
    save()
    (root/'latest-workload-guard').write_text(str(report))
    try:
        while not STOP and time.clock_gettime(CLOCK)-start<a.seconds:
            if identity(a.unit)!=owned:
                result.update(status='workload_changed_or_exited');break
            try:
                row=latest(Path('/var/lib/g965n-charge-observer/samples.jsonl'))
                voltage=int(Path('/sys/class/power_supply/max170xx_battery/voltage_now').read_text())
                reason=trip_reason(row,time.clock_gettime_ns(CLOCK),voltage,a.battery_stop_deci_c)
            except (OSError,ValueError):reason='unreadable_measurement';voltage=None;row={}
            result.update(elapsed_seconds=round(time.clock_gettime(CLOCK)-start,1),voltage_uv=voltage,
                temperature=row.get('temperature',{}),reason=reason)
            if reason:
                # Preserve another invocation even if the service name is reused.
                if identity(a.unit)==owned:
                    action=subprocess.run(['systemctl','stop','--',a.unit],timeout=15,check=False)
                    result.update(status='stopped_owned_workload' if action.returncode==0 else 'stop_failed')
                else:result.update(status='workload_changed_before_stop')
                save();break
            save();time.sleep(1)
        else:result['status']='interrupted' if STOP else 'completed_observation'
    finally:
        # The explicitly selected trial must not outlive its own supervision.
        # Reused names/new invocations are never stopped by this cleanup.
        if identity(a.unit)==owned:
            action=subprocess.run(['systemctl','stop','--',a.unit],timeout=15,check=False)
            result.update(cleanup='stopped_owned_workload' if action.returncode==0 else 'stop_failed')
        save()
    save();print(json.dumps({k:v for k,v in result.items() if k!='unit'}),flush=True)

if __name__=='__main__':main()

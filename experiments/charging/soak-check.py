#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only bounded charging qualification; never controls charger hardware."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

ROOT=Path('/var/lib/g965n-charge-observer')
STOP=False
CLOCK=getattr(time,'CLOCK_BOOTTIME',time.CLOCK_MONOTONIC)
def now_seconds():return time.clock_gettime(CLOCK)
def now_ns():return time.clock_gettime_ns(CLOCK)


def latest():
    for line in reversed((ROOT/'samples.jsonl').read_text().splitlines()):
        try:row=json.loads(line)
        except json.JSONDecodeError:continue
        if 'end_monotonic_ns' in row:return row
    raise RuntimeError('No completed sample')


def classify(row,now,guardian=None,source_policy=None):
    faults=[];conditions=[]
    if guardian and guardian.get('hardware_fault'):faults.append('latched_hardware_fault')
    if guardian and guardian.get('configuration_fault'):faults.append('latched_configuration_drift')
    if guardian and guardian.get('reasons'):conditions.append('protection_pause')
    if not 0<=now-row.get('end_monotonic_ns',-100_000_000_000)<35_000_000_000:
        return faults,conditions+['stale_record']
    d=row.get('decoded',{})
    if d.get('charge') in (5,6,7,10,11,12):faults.append('hardware_charge_fault')
    if row.get('source_initialization_mismatch'):faults.append('configuration_drift')
    if 'source_initialization_mismatch' not in row:conditions.append('missing_configuration')
    if row.get('temperature_error') or not row.get('shadow_thermal_policy',{}).get('valid'):conditions.append('invalid_temperature')
    if d.get('input')!=3:conditions.append('input_changed')
    if d.get('charge_enabled')!=1 or d.get('charge') not in (0,1,2,3):conditions.append('charging_interrupted_or_completed')
    supply=row.get('power_supply',{}).get('max77705-charger',{})
    expected_input = '500000'
    if source_policy is not None:
        target=source_policy.get('expected',900000)
        if target not in (900000,1200000) or source_policy.get('ceiling') != target:
            conditions.append('input_lease_not_active')
        expected_input = str(target)
    if supply.get('input_current_limit')!=expected_input or supply.get('constant_charge_current')!='450000' or supply.get('constant_charge_voltage')!='4350000':conditions.append('baseline_limits_changed')
    return faults,conditions


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-read-only-soak',action='store_true',required=True)
    p.add_argument('--seconds',type=int,default=10800);p.add_argument('--interval',type=int,default=15)
    p.add_argument('--with-input-source-lease',action='store_true')
    p.add_argument('--input-limit-ua',type=int,choices=(900000,1200000),default=900000,
                   help='Expected limit only when --with-input-source-lease is used')
    p.add_argument('--require-active-unit',help='Observe a workload service without starting/stopping it')
    a=p.parse_args()
    if not 30<=a.seconds<=12600 or not 1<=a.interval<=60:raise RuntimeError('Unbounded duration/interval refused')
    if os.geteuid()!=0:raise RuntimeError('Root required')
    spec=importlib.util.spec_from_file_location('guard','/usr/local/lib/g965n-led-trial/led-control.py')
    g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.preflight()
    policy = None
    if a.with_input_source_lease:
        spec=importlib.util.spec_from_file_location('guardian',Path(__file__).with_name('charge-guardian.py'))
        policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
    os.umask(0o077);report=Path(tempfile.mkdtemp(prefix='soak-',dir=ROOT));boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    def stop(*_):
        global STOP
        STOP=True
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    start=now_seconds();seen=None;currents=[];faults=set();conditions=set();count=0
    summary={'status':'running','target_seconds':a.seconds,'boot_id':boot,'kernel_version':os.uname().version,'kernel_release':os.uname().release,'started_utc':datetime.now(timezone.utc).isoformat()}
    (ROOT/'latest-soak-path').write_text(str(report))
    while not STOP and now_seconds()-start<a.seconds:
        if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=boot:
            conditions.add('boot_changed');break
        try:
            row=latest();guardian=json.loads(Path('/var/lib/g965n-charge-guardian/state.json').read_text())
            source_policy=None
            if policy:
                row['input_source_policy']=policy.input_source_policy()
                source_policy={'ceiling':policy.input_ceiling(row,now_ns()),'expected':a.input_limit_ua}
                if guardian.get('boot')!=boot or not 0<=now_seconds()-guardian.get('last',-100)<=15:
                    conditions.add('guardian_not_fresh')
            bad,changed=classify(row,now_ns(),guardian,source_policy);faults.update(bad);conditions.update(changed)
            if a.require_active_unit and subprocess.run(['systemctl','is-active','--quiet','--',a.require_active_unit],check=False).returncode:
                conditions.add('required_workload_not_active')
            if row.get('end_monotonic_ns')!=seen:
                count+=1;seen=row.get('end_monotonic_ns')
                value=row['power_supply']['max170xx_battery']['current_avg'];currents.append(int(value))
        except (OSError,ValueError,KeyError,RuntimeError):conditions.add('unreadable_sample')
        summary.update(elapsed_seconds=round(now_seconds()-start,1),samples=count,faults=sorted(faults),conditions=sorted(conditions))
        if faults:summary['status']='failed'
        with tempfile.NamedTemporaryFile(mode='w',dir=report,delete=False) as file:
            json.dump(summary,file);file.flush();os.fsync(file.fileno());tmp=Path(file.name)
        tmp.replace(report/'result.json')
        if faults:break
        for _ in range(a.interval*5):
            if STOP:break
            time.sleep(.2)
    if STOP:conditions.add('interrupted')
    if count<max(3,int(a.seconds/max(15,a.interval)*.7)):conditions.add('insufficient_samples')
    mean=sum(currents)/len(currents) if currents else None
    if mean is None or mean<=0:conditions.add('no_reported_net_charging')
    summary.update(elapsed_seconds=round(now_seconds()-start,1),samples=count,faults=sorted(faults),conditions=sorted(conditions),reported_net_current_average_ua=mean)
    summary['status']='failed' if faults else 'inconclusive' if conditions else 'passed'
    (report/'result.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='boot_id'}),flush=True)
    if faults:raise SystemExit(1)


if __name__=='__main__':main()

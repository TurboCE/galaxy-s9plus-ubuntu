#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Add only owned audit watches; never clear other rules or enable global audit."""
from pathlib import Path
import shutil
import subprocess

KEY='g965n_charge_control'
CONTROLS=('charge_behaviour','constant_charge_current','input_current_limit')


def configure():
    tool=shutil.which('auditctl')
    if not tool: return {'available':False,'reason':'auditctl unavailable'}
    status=subprocess.run([tool,'-s'],capture_output=True,text=True,timeout=5)
    enabled=next((line.split()[1] for line in status.stdout.splitlines() if line.startswith('enabled ')),None)
    if status.returncode or enabled not in ('1','2'):
        return {'available':False,'reason':'audit not enabled; global policy unchanged'}
    rules=subprocess.run([tool,'-l'],capture_output=True,text=True,timeout=5)
    if rules.returncode: return {'available':False,'reason':'audit rule enumeration failed'}
    result={}
    controls=list(CONTROLS)
    if (Path('/sys/class/power_supply/max77705-charger')/'device/charge_policy_request').exists():
        controls.append('device/charge_policy_request')
    for name in controls:
        node=Path('/sys/class/power_supply/max77705-charger')/name
        if not node.exists():
            result[name]={'error':'control missing'};continue
        path=str(node.resolve())
        expected=f'-w {path} -p w -k {KEY}'
        if expected in rules.stdout.splitlines():
            result[name]={'watched':True};continue
        if enabled=='2':
            result[name]={'error':'immutable audit configuration'};continue
        added=subprocess.run([tool,'-w',path,'-p','w','-k',KEY],capture_output=True,text=True,timeout=5)
        result[name]={'watched':added.returncode==0}
        if added.returncode: result[name]['error']=added.stderr.strip()[:200]
    return {'available':all(v.get('watched',False) for v in result.values()),'controls':result}


if __name__=='__main__':
    import argparse,importlib.util,json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-sm-g965n-backed-up-audit',required=True,action='store_true')
    parser.parse_args()
    spec=importlib.util.spec_from_file_location('guard','/usr/local/lib/g965n-led-trial/led-control.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);guard.preflight()
    print(json.dumps(configure()))

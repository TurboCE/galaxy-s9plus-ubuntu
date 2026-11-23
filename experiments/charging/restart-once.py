#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit one-shot CHG-edge diagnostic; never a periodic fault-reset policy."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time


def eligible(row, now, limits):
    age=now-row.get('end_monotonic_ns',-100000000000)
    thermal=row.get('shadow_thermal_policy',{})
    return (0<=age<30_000_000_000 and
        row.get('decoded')=={'charge':6,'battery':2,'input':3,'charge_enabled':1} and
        thermal.get('valid') is True and thermal.get('thermal_charge_permission') is True and
        thermal.get('swelling_high_temperature_policy_required') is False and
        100<=row.get('temperature',{}).get('battery',{}).get('temperature_deci_c',-999)<400 and
        limits=={'input_current_limit':'500000','constant_charge_current':'450000','constant_charge_voltage':'4200000'})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-measured-sm-g965n-fault-once',action='store_true',required=True)
    parser.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Root required')
    os.umask(0o077)
    spec=importlib.util.spec_from_file_location('guard','/usr/local/lib/g965n-led-trial/led-control.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);guard.preflight()
    charger=Path('/sys/class/power_supply/max77705-charger');battery=Path('/sys/class/power_supply/max170xx_battery')
    rows=[json.loads(line) for line in Path('/var/lib/g965n-charge-observer/samples.jsonl').read_text().splitlines()]
    row=next(r for r in reversed(rows) if 'temperature' in r)
    limits={k:(charger/k).read_text().strip() for k in ('input_current_limit','constant_charge_current','constant_charge_voltage')}
    if (not eligible(row,time.monotonic_ns(),limits) or int((battery/'capacity').read_text())<10 or
            int((battery/'voltage_now').read_text())<3600000 or
            (charger/'online').read_text().strip()!='1' or '[auto]' not in (charger/'charge_behaviour').read_text()):
        raise RuntimeError('Measured fault/temperature/power/intent does not qualify this bounded trial')
    fd=os.open('/run/g965n-charge-edge-trial',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    receipt=Path(tempfile.mkdtemp(prefix='charge-edge-trial-',dir='/var/lib/g965n-sensors'))
    (receipt/'before.json').write_text(json.dumps(row))
    try:
        (charger/'charge_behaviour').write_text('inhibit-charge\n');time.sleep(.3)
        if '[inhibit-charge]' not in (charger/'charge_behaviour').read_text():
            raise RuntimeError('Disable readback failed')
    finally:
        (charger/'charge_behaviour').write_text('auto\n')
    for i in range(6):
        time.sleep(5)
        result={k:(charger/k).read_text().strip() for k in ('status','health','charge_behaviour')}
        result.update({k:int((battery/k).read_text()) for k in ('voltage_now','current_now','current_avg','capacity')})
        (receipt/f'after-{i}.json').write_text(json.dumps(result));print(json.dumps(result),flush=True)
    if limits!={k:(charger/k).read_text().strip() for k in limits}:
        raise RuntimeError('Unexpected charger-limit change; preserve evidence')


if __name__=='__main__':main()

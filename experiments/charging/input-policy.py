#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded 900/1200mA input trial; kernel owns source checks and 15s lease expiry.

Never changes CV, charge current, CHG intent or temperature thresholds.
"""
import argparse
import errno
import importlib.util
import json
import os
from pathlib import Path
import signal
import time

DEV = Path('/sys/bus/i2c/devices/3-0025')
STOP = False
CLOCK = getattr(time, 'CLOCK_BOOTTIME', time.CLOCK_MONOTONIC)

def permitted(row, now):
    try:
        if not 0 <= now-row['end_monotonic_ns'] < 35_000_000_000:return False
        t = row['temperature']
        if row.get('temperature_error'):return False
        # External system power is distinct from permission to charge the pack.
        # The independent guardian still inhibits CHG at41C/recover39C.
        for key, low, high in (('battery',0,430),('usb',0,450),('charger',0,500)):
            value = t[key]['temperature_deci_c']
            if type(value) is not int or not low <= value <= high:return False
        d = row['decoded']
        return (d['input'] == 3 and d['battery'] in (1,3,4) and d['charge'] in (0,1,2,3,4,8)
            and row['source_initialization_mismatch'] == {})
    except (KeyError,TypeError,ValueError):
        return False

def guardian_ready(state, now, boot):
    """Benign battery-charge holds need not deprive the system of input power."""
    benign={'swelling_temperature_stop','full_stop','full_hold','safety_time_expired'}
    try:
        return (state.get('hardware_fault') is False and state.get('configuration_fault') is False and
            state.get('boot')==boot and 0<=now-state['last']<=15 and
            isinstance(state['reasons'],list) and all(x in benign for x in state['reasons']))
    except (KeyError,TypeError):return False


def control():
    c = [int(v) for v in (DEV/'input_policy_state').read_text().split()]
    if len(c) != 5:raise RuntimeError('Invalid kernel lease state')
    return dict(zip(('generation','owned','requested','applied','deadline_ms'),c))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-backed-up-input-trial',required=True,action='store_true')
    p.add_argument('--seconds',type=int,default=600)
    p.add_argument('--input-limit-ua',type=int,choices=(900000,1200000),default=900000)
    a=p.parse_args()
    if not 1 <= a.seconds <= 86400:p.error('Bounded trial: 1..86400 seconds')
    if os.geteuid()!=0:raise RuntimeError('Root required')
    s=importlib.util.spec_from_file_location('g','/usr/local/lib/g965n-led-trial/led-control.py')
    g=importlib.util.module_from_spec(s);s.loader.exec_module(g);g.preflight()
    s=importlib.util.spec_from_file_location('guardian',Path(__file__).with_name('charge-guardian.py'))
    guardian=importlib.util.module_from_spec(s);s.loader.exec_module(guardian)
    if (DEV/'driver').resolve().name not in ('s9p-max77705-muic','s9p-max77705-muic-source'):
        raise RuntimeError('Unqualified source owner')
    c=control()
    if c['owned']:raise RuntimeError('Preserve an existing input lease')
    generation=c['generation']
    def stop(*_):
        global STOP
        STOP=True
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
    end=time.clock_gettime(CLOCK)+a.seconds
    held=True;previous=None
    def release_owned(token):
        state=control()
        if state['generation']!=token:
            raise RuntimeError('External input ownership change; do not reacquire')
        if not state['owned']:return token
        (DEV/'input_policy_request').write_text(f'{token} 0\n')
        state=control()
        if state['generation']!=token+1 or state['owned']:
            raise RuntimeError('Concurrent input change during release')
        return state['generation']
    try:
        while not STOP and time.clock_gettime(CLOCK)<end:
            c=control()
            if c['generation']!=generation:
                raise RuntimeError('Kernel lease revoked; preserve external input request')
            row=guardian.sample()
            state=json.loads(Path('/var/lib/g965n-charge-guardian/state.json').read_text())
            if state.get('hardware_fault') or state.get('configuration_fault'):
                raise RuntimeError('Latched guardian fault; no automatic retry')
            healthy=(permitted(row,time.clock_gettime_ns(CLOCK)) and
                guardian_ready(state,time.clock_gettime(CLOCK),Path('/proc/sys/kernel/random/boot_id').read_text().strip()))
            # Input-only hysteresis; the independent CHG41/39C gate is unchanged.
            if held and healthy:
                t=row['temperature']
                healthy=(t['battery']['temperature_deci_c']<=410 and
                         t['usb']['temperature_deci_c']<=430 and t['charger']['temperature_deci_c']<=480)
            if not healthy:
                generation=release_owned(generation);held=True
                action='protection_hold'
            else:
                try:
                    (DEV/'input_policy_request').write_text(f'{generation} {a.input_limit_ua}\n')
                except OSError as error:
                    if error.errno!=errno.ENODATA:raise
                    generation=release_owned(generation);held=True;action='source_hold'
                else:
                    c=control()
                    if c['generation']!=generation:
                        raise RuntimeError('External controller changed input')
                    if not c['owned'] or c['applied']!=a.input_limit_ua:
                        generation=release_owned(generation);held=True;action='source_hold'
                    else:
                        held=False;action='lease_live'
            if action!=previous:
                print(json.dumps({'input_policy':action,'input_limit_ua':a.input_limit_ua if action=='lease_live' else 500000,'remaining_seconds':round(end-time.clock_gettime(CLOCK))}),flush=True)
                previous=action
            for _ in range(25):
                if STOP:break
                time.sleep(.2)
    finally:
        # An external/revoked generation is never reacquired automatically.
        try:release_owned(generation)
        except (OSError,RuntimeError):pass  # Independent kernel expiry still applies.

if __name__=='__main__':main()

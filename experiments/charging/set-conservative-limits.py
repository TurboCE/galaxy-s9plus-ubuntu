#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reduce inherited input/charge current ceilings; never increases either."""
import argparse
import importlib.util
import json
import os
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--confirm-sm-g965n-current-reduction',required=True,action='store_true');p.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Root required')
    s=importlib.util.spec_from_file_location('guard','/usr/local/lib/g965n-led-trial/led-control.py')
    g=importlib.util.module_from_spec(s);s.loader.exec_module(g);g.preflight()
    root=Path('/sys/class/power_supply/max77705-charger');result={}
    for name,ceiling in (('input_current_limit',500000),('constant_charge_current',450000)):
        before=int((root/name).read_text());target=min(before,ceiling)
        if before<=0:raise RuntimeError('Invalid current readback')
        if target<before:(root/name).write_text(str(target)+'\n')
        after=int((root/name).read_text())
        if after>target or after<=0:raise RuntimeError('Conservative ceiling readback failed')
        result[name]={'before':before,'after':after}
    print(json.dumps({'current_reduction':result}),flush=True)


if __name__=='__main__':main()

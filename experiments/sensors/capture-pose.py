#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture one explicitly labeled private pose; never infer/apply orientation."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import time

SPEC=importlib.util.spec_from_file_location('ssp_pose',Path(__file__).with_name('ssp-probe.py'))
SSP=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(SSP)
POSES=('top-up','top-right','top-left','bottom-up','face-up','face-down')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',choices=['SM-G965N'],required=True)
    p.add_argument('--pose',choices=POSES,required=True)
    p.add_argument('--output',type=Path,required=True,help='New private file; overwriting is refused')
    args=p.parse_args()
    if os.geteuid()!=0:p.error('Use the already verified native root sensor environment')
    SSP.require_board();SSP.require_transport_ready()
    parent=args.output.parent.resolve(strict=True);info=parent.stat()
    if info.st_uid!=0 or info.st_mode&0o077:p.error('Output parent must be root-owned/private')
    if args.output.exists() or args.output.is_symlink():p.error('Preserve old observations; choose a new output file')
    with SSP.acquire_probe_lock():
        probe=SSP.Probe();enabled=[]
        try:
            identity=SSP.acquire_hub_identity(probe)
            SSP.require_advertised([0],identity['sensor_mask'])
            if probe.transaction(0xE1,length=1)!=b'\x08':raise RuntimeError('Require actual8G range before capture')
            enabled.append(0)
            probe.transaction(0xA1,struct.pack('<BiiB',0,SSP.SAMPLE_DELAY_MS,0,0))
            probe.samples[0]=[];until=time.monotonic()+8
            while time.monotonic()<until:probe.pump(.1)
            frames=probe.samples[0][-20:]
            if len(frames)<12:raise RuntimeError('Not enough actual samples; no observation file created')
            result={'pose':args.pose,'frames':frames,'identity':identity,'range_g':8,
                    'model':args.model,'kernel_version':os.uname().version,
                    'physical_label':'Operator supplied; evaluate geometry independently'}
            fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as stream:json.dump(result,stream);stream.flush();os.fsync(stream.fileno())
            print('Private pose captured; no mounting matrix applied')
        finally:
            try:SSP.disable_sensors(probe,enabled)
            finally:os.close(probe.fd)

if __name__=='__main__':main()

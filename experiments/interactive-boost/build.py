#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build one guarded optional input-QoS module; never install, load or flash."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--kernel-source', type=Path, required=True)
p.add_argument('--kernel-out', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--with-cap-test', action='store_true', help='Build the separate opt-in lower-MAX QA helper')
a = p.parse_args()
here = Path(__file__).resolve().parent
pins = json.loads((here / 'TRIAL.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
source, out, work = a.kernel_source.resolve(), a.kernel_out.resolve(), a.output.absolute()
if work.exists() or work.is_symlink() or work.is_relative_to(source) or work.is_relative_to(out):
    p.error('Use a new isolated output directory')
if sha(out / 'Module.symvers') != pins['module_symvers_sha256']:
    p.error('Kernel ABI differs from qualified native48')
for name, expected in pins['source_sha256'].items():
    if sha(here / name) != expected:
        p.error('Reviewed source pin drifted')
work.mkdir(mode=0o700)
for name in ('Makefile', 'g965n-interactive-boost.c', 'g965n-qos-cap-test.c'):
    shutil.copyfile(here / name, work / name)
subprocess.run(['make', '-s', '-C', str(source), 'O='+str(out), 'ARCH=arm64',
                'CROSS_COMPILE=aarch64-linux-gnu-', 'M='+str(work),
                'KCFLAGS=-Werror', *(['G965N_QOS_CAP_TEST=m'] if a.with_cap_test else []), 'modules'], check=True)
(work / 'pins.json').write_text(json.dumps({'g965n-interactive-boost.ko':sha(work / 'g965n-interactive-boost.ko')}, indent=2)+'\n')
print('Input-QoS module built; no installation/load/flash')

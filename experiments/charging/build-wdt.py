#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only MAX77705 watchdog experiment; never loads or flashes."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser(description=__doc__)
for key in ('kernel-source', 'kernel-out', 'output'):
    p.add_argument('--' + key, type=Path, required=True)
a = p.parse_args()
source, out, work = a.kernel_source.resolve(), a.kernel_out.resolve(), a.output.resolve()
if work.exists() or a.output.is_symlink() or work.is_relative_to(source) or work.is_relative_to(out):
    p.error('New isolated output required')
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
pins = {
    'include/linux/mfd/max77705-private.h': '5578656274bca0afbf4852a74dd65562efffbe7475dd1631b3a042820a02e00f',
    'include/linux/power/max77705_charger.h': 'fd259f85a2f6aaf968903277d0b184b89cefde55326ab43a25f1bd786612151a',
}
for name, expected in pins.items():
    if sha(source / name) != expected:
        p.error('Unqualified native header: ' + name)
if sha(out / 'Module.symvers') != '45d68e3278f2498bb2d187c86b86c2803417d2c4dbcccbe096caf268dd6422e2':
    p.error('Unqualified native export ABI')
work.mkdir(mode=0o700)
src = Path(__file__).with_name('g965n-charge-wdt.c')
shutil.copyfile(src, work / src.name)
(work / 'Makefile').write_text('obj-m += g965n-charge-wdt.o\n')
subprocess.run(['make', '-s', '-C', str(source), 'O=' + str(out), 'ARCH=arm64',
                'CROSS_COMPILE=aarch64-linux-gnu-', 'M=' + str(work), 'KCFLAGS=-Werror', 'modules'], check=True)
(work / 'pins.json').write_text(json.dumps({'source_sha256': sha(src), 'headers': pins,
    'module_sha256': sha(work / 'g965n-charge-wdt.ko')}, indent=2) + '\n')
print('Watchdog qualification module built; no device writes')

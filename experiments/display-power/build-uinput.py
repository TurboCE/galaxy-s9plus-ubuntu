#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build unmodified Linux uinput for the qualified native ABI; never loads/flashes."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ('kernel-source','kernel-out','output'):p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args();src=a.kernel_source.resolve();out=a.kernel_out.resolve();work=a.output.resolve()
if work.exists() or a.output.is_symlink() or work.is_relative_to(src) or work.is_relative_to(out):p.error('New isolated output required')
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
if sha(out/'Module.symvers')!='45d68e3278f2498bb2d187c86b86c2803417d2c4dbcccbe096caf268dd6422e2':p.error('Unqualified export ABI')
reference=json.loads(Path(__file__).with_name('UINPUT_REFERENCE.json').read_text())
for name,digest in reference['inputs'].items():
 if sha(src/name)!=digest:p.error('Unqualified Linux uinput source/header')
work.mkdir(mode=0o700);(work/'misc').mkdir(mode=0o700)
# Preserve upstream code, SPDX and every original notice byte-for-byte.
shutil.copyfile(src/'drivers/input/misc/uinput.c',work/'misc/uinput.c')
shutil.copyfile(src/'drivers/input/input-compat.h',work/'input-compat.h')
(work/'misc/Makefile').write_text('obj-m += uinput.o\n')
subprocess.run(['make','-s','-C',str(src),'O='+str(out),'ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-','M='+str(work/'misc'),'KCFLAGS=-Werror','modules'],check=True)
(work/'pins.json').write_text(json.dumps({'uinput.ko':sha(work/'misc/uinput.ko')},indent=2)+'\n')
print('Unmodified GPL Linux uinput module built; no device writes')

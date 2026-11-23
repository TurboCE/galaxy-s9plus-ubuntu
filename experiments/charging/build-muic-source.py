#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only reversible MUIC source/lease module. Never loads or flashes."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for key in ('kernel-source','kernel-out','output'):
 p.add_argument('--'+key,type=Path,required=True)
a=p.parse_args()
source=a.kernel_source.resolve();out=a.kernel_out.resolve();work=a.output.resolve()
if work.exists() or a.output.is_symlink() or work.is_relative_to(source) or work.is_relative_to(out):
 p.error('New isolated output required')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if sha(out/'Module.symvers')!='45d68e3278f2498bb2d187c86b86c2803417d2c4dbcccbe096caf268dd6422e2':
 p.error('Unqualified native export ABI')
repo=Path(__file__).resolve().parents[2]
work.mkdir(mode=0o700)
inputs={}
for src,dst in [('src/soc/s9p-max77705-muic.c','g965n-muic-source.c'),('src/soc/s9p-max77705-source.h','s9p-max77705-source.h')]:
 shutil.copyfile(repo/src,work/dst);inputs[src]=sha(repo/src)
(work/'Makefile').write_text('obj-m += g965n-muic-source.o\nccflags-y += -DS9P_MUIC_DRIVER_NAME=\'"s9p-max77705-muic-source"\'\n')
subprocess.run(['make','-s','-C',str(source),'O='+str(out),'ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-','M='+str(work),'KCFLAGS=-Werror','modules'],check=True)
(work/'pins.json').write_text(json.dumps({'inputs':inputs,'module_sha256':sha(work/'g965n-muic-source.ko')},indent=2)+'\n')
print('MUIC query/lease module built; no device writes')

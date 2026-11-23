#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only read-only USB-C source diagnostic; never loads/flashes/writes ICs."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ('kernel-source','kernel-out','output'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();source=a.kernel_source.resolve();out=a.kernel_out.resolve();work=a.output.absolute()
if work.exists() or work.is_symlink() or work.is_relative_to(source) or work.is_relative_to(out):p.error('New isolated output required')
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
if sha(out/'Module.symvers')!='45d68e3278f2498bb2d187c86b86c2803417d2c4dbcccbe096caf268dd6422e2':p.error('Unqualified native ABI')
work.mkdir(mode=0o700);shutil.copyfile(Path(__file__).parent/'g965n-usbc-source.c',work/'g965n-usbc-source.c')
(work/'Makefile').write_text('obj-m += g965n-usbc-source.o\n')
subprocess.run(['make','-s','-C',str(source),'O='+str(out),'ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-','M='+str(work),'KCFLAGS=-Werror','modules'],check=True)
(work/'pins.json').write_text(json.dumps({'g965n-usbc-source.ko':sha(work/'g965n-usbc-source.ko')},indent=2)+'\n')
print('Read-only source diagnostic built; no device writes')

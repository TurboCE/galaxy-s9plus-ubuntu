#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Isolated build-only incremental trial; preserve qualified base objects.

Uses reviewed recorded compile/link commands, including kallsyms verification.
Never installs modules, writes devices or modifies the source/base output tree.
"""
from pathlib import Path
import argparse,subprocess,shlex,os,json,hashlib,datetime
p=argparse.ArgumentParser(description='Build-only #49 charging trial from the qualified #48 output; never flashes')
p.add_argument('--base-out',type=Path,required=True)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--candidate-source',type=Path,required=True)
p.add_argument('--qualified-symvers',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--build-number',type=int,choices=(49,50),default=49)
p.add_argument('--timestamp',help='Optional exact UTC UTS timestamp for reproduction')
a=p.parse_args();os.umask(0o077)
base=a.base_out.resolve();source=a.source.resolve();stage=a.output.resolve()
if stage.exists():raise RuntimeError('Output must be new')
if hashlib.sha256(a.qualified_symvers.read_bytes()).hexdigest()!='45d68e3278f2498bb2d187c86b86c2803417d2c4dbcccbe096caf268dd6422e2':raise RuntimeError('Unqualified export ABI')
if hashlib.sha256((base/'arch/arm64/boot/Image').read_bytes()).hexdigest()!='4c124c7b1f69d362227ebb34e4b6ec7a3f877b8069c6195b9dcf3c88e24a98c2':raise RuntimeError('Unqualified base Image')
stage.mkdir(mode=0o700);out=stage/'out'
(stage/'max77705_charger.c').write_bytes(a.candidate_source.read_bytes())
subprocess.run(['cp','-a',str(base),str(out)],check=True)
# Recompile only the reviewed charger and build-identity object in a private
# qualified output copy; keep all unrelated device fixes/initramfs intact.
def command(path):return (base/path).read_text().splitlines()[0].split(' := ',1)[1].strip()
cmd=shlex.split(command('drivers/power/supply/.max77705_charger.o.cmd'))
old=str(source/'drivers/power/supply/max77705_charger.c');assert cmd.count(old)==1
cmd[cmd.index(old)]=str(stage/'max77705_charger.c')
subprocess.run(cmd,cwd=out,check=True)
fmt='%a %b %d %H:%M:%S UTC %Y'
stamp=a.timestamp or datetime.datetime.now(datetime.timezone.utc).strftime(fmt)
if datetime.datetime.strptime(stamp,fmt).strftime(fmt)!=stamp:raise ValueError('Invalid exact UTC timestamp')
(out/'include/generated/utsversion.h').write_text('#define UTS_VERSION "#'+str(a.build_number)+' SMP PREEMPT '+stamp+'"\n')
subprocess.run(shlex.split(command('init/.version-timestamp.o.cmd')),cwd=out,check=True)
subprocess.run(command('.vmlinux.o.cmd'),shell=True,cwd=out,check=True)
env=os.environ.copy();env.update(srctree=str(source),objtree='.',SRCARCH='arm64',ARCH='arm64',
 MAKE='true',CC='aarch64-linux-gnu-gcc',NM='aarch64-linux-gnu-nm',OBJCOPY='aarch64-linux-gnu-objcopy',
 CONFIG_SHELL='/bin/sh',KBUILD_LDS='arch/arm64/kernel/vmlinux.lds',KBUILD_VMLINUX_LIBS='',KBUILD_VERBOSE='0',
 LINUXINCLUDE='-I'+str(source/'arch/arm64/include')+' -Iarch/arm64/include/generated -I'+str(source/'include')+' -Iinclude',
 KBUILD_CPPFLAGS='-D__KERNEL__ -D__ASSEMBLY__',KBUILD_AFLAGS='-mlittle-endian -Wa,-march=armv8.5-a')
subprocess.run(command('.vmlinux.unstripped.cmd').removesuffix(';  true'),shell=True,cwd=out,env=env,check=True)
subprocess.run(command('.vmlinux.cmd'),shell=True,cwd=out,check=True)
subprocess.run(command('arch/arm64/boot/.Image.cmd'),shell=True,cwd=out,check=True)
image=(out/'arch/arm64/boot/Image').read_bytes();assert ('#'+str(a.build_number)+' SMP PREEMPT ').encode() in image and image[56:60]==b'ARM\x64'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(stage/'kernel-build.json').write_text(json.dumps({'base_image':sha(base/'arch/arm64/boot/Image'),'image':sha(out/'arch/arm64/boot/Image'),'charger_source':sha(stage/'max77705_charger.c'),'uts':stamp,'build_number':a.build_number,'mode':'isolated incremental relink; charger and timestamp only'},indent=2))
print('PRIVATE #49 Image built; no device writes',flush=True)

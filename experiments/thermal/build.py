#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only isolated thermal QoS module against qualified native ABI; never flashes."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
for n in ('kernel-source','kernel-out','output'):p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--with-gpu-snapshot',action='store_true')
a=p.parse_args();src=a.kernel_source.resolve();out=a.kernel_out.resolve();work=a.output.absolute()
if work.exists() or work.is_symlink() or work.is_relative_to(src) or work.is_relative_to(out):p.error('New isolated output required')
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
if sha(out/'Module.symvers')!='45d68e3278f2498bb2d187c86b86c2803417d2c4dbcccbe096caf268dd6422e2':p.error('Unqualified ABI')
if a.with_gpu_snapshot:
    for name,expected in json.loads((Path(__file__).parent/'SNAPSHOT_LAYOUT.json').read_text()).items():
        if sha(src/'drivers/gpu/drm/panfrost'/name)!=expected:p.error('Unqualified Panfrost private layout')
work.mkdir(mode=0o700)
for n in ('Makefile','g965n-thermal-qos.c','g965n-gpu-idle-snapshot.c'):shutil.copyfile(Path(__file__).parent/n,work/n)
subprocess.run(['make','-s','-C',str(src),'O='+str(out),'ARCH=arm64','CROSS_COMPILE=aarch64-linux-gnu-','M='+str(work),'KCFLAGS=-Werror',*(['G965N_GPU_SNAPSHOT=m'] if a.with_gpu_snapshot else []),'modules'],check=True)
(work/'pins.json').write_text(json.dumps({'g965n-thermal-qos.ko':sha(work/'g965n-thermal-qos.ko')},indent=2)+'\n')
print('Module built; no device writes')

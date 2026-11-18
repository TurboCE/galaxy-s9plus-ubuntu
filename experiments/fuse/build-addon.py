#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only, exact-kernel21 in-tree FUSE compatibility add-on. No device access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess

HEAD = '8cd9520d35a6c38db6567e97dd93b1f11f185dc6'
CONFIG_SHA = '71e2df2692ff368b642756cbd66a2b4117d9aeb102fe8dce2f76db107e461f0a'
VMLINUX_SHA = '01b16afc87d0b41f3073f2c4f4e941e659ae4757b0e305b2d0d644a5a490c2bc'
SYMVERS_SHA = '11b780dda68ae6c544ceaa6fd4890bd2dc331743763ff2dcff456f02c5d839f0'
COMPILER = 'aarch64-linux-gnu-gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0'
VERSION = '#21 SMP PREEMPT Wed Nov 18 20:51:24 UTC 2026'
RELEASE = '7.1.0-dirty'
VFS = ['include/linux/fs.h','include/uapi/linux/fuse.h',
       'include/linux/uio.h','include/linux/file.h','include/linux/mount.h',
       'include/linux/namei.h','include/linux/pagemap.h']


def sha(data): return hashlib.sha256(data).hexdigest()


def run(args, **kw):
    return subprocess.check_output(args, text=True, **kw).strip()


def module_info(data):
    """Read only ELF section headers and .modinfo; never execute the module."""
    if len(data)<64 or data[:7]!=b'\x7fELF\x02\x01\x01':
        raise ValueError('Expected ELF64 little-endian module')
    if struct.unpack_from('<HH',data,16)!=(1,183):
        raise ValueError('Expected AArch64 ET_REL module')
    off=struct.unpack_from('<Q',data,40)[0]
    size,count,strings=struct.unpack_from('<HHH',data,58)
    if size!=64 or not 0<strings<count<=4096 or off+size*count>len(data):
        raise ValueError('Invalid ELF section table')
    def section(i):
        h=off+i*size
        start,length=struct.unpack_from('<QQ',data,h+24)
        if start+length>len(data):raise ValueError('ELF section exceeds file')
        return data[start:start+length]
    names=section(strings)
    matches=[]
    for i in range(count):
        n=struct.unpack_from('<I',data,off+i*size)[0]
        if n>=len(names):raise ValueError('Invalid ELF section name')
        if names[n:].split(b'\0',1)[0]==b'.modinfo':matches.append(section(i))
    if len(matches)!=1:raise ValueError('Expected one modinfo section')
    result={}
    for raw in matches[0].split(b'\0'):
        if b'=' not in raw:continue
        key,value=raw.split(b'=',1)
        key=key.decode('ascii');value=value.decode('ascii')
        result.setdefault(key,[]).append(value)
    if result.get('name')!=['fuse'] or result.get('license')!=['GPL']:
        raise ValueError('Expected GPL fuse module')
    if result.get('depends') not in (None,['']):
        raise ValueError('Unexpected FUSE module dependencies')
    vermagic=result.get('vermagic',[])
    if len(vermagic)!=1 or vermagic[0].split()!=[RELEASE,'SMP','preempt','mod_unload','aarch64']:
        raise ValueError('Unexpected module vermagic')
    if 'modversions' in vermagic[0].split():raise ValueError('Unexpected MODVERSIONS ABI')
    return result


def inspect(source,out,native_config,startup,boot):
    if run(['git','-C',str(source),'rev-parse','HEAD'])!=HEAD:raise ValueError('Wrong upstream source commit')
    if run(['git','-C',str(source),'status','--porcelain','--untracked-files=all','--','fs/fuse',*VFS]):
        raise ValueError('Unreviewed FUSE/VFS source changes')
    subprocess.run(['git','-C',str(source),'diff','--exit-code','HEAD','--','fs/fuse',*VFS],check=True,stdout=subprocess.DEVNULL)
    # All tracked common/architecture headers must retain the upstream ABI,
    # not merely the small set explicitly listed in the diagnostic receipt.
    subprocess.run(['git','-C',str(source),'diff','--exit-code','HEAD','--',
                    'include','arch/arm64/include'],check=True,stdout=subprocess.DEVNULL)
    config=(out/'.config').read_bytes()
    if sha(config)!=CONFIG_SHA or native_config.read_bytes()!=config:raise ValueError('Config is not exact native21 config')
    for option in ['CONFIG_FUSE_FS=m','CONFIG_CUSE=m','# CONFIG_MODVERSIONS is not set']:
        if option not in config.decode().splitlines():raise ValueError('Unexpected FUSE/kernel ABI config')
    kernel=json.loads(startup.read_text())
    if kernel.get('model')!='SM-G965N' or kernel.get('kernel_release')!=RELEASE or kernel.get('kernel_version')!=VERSION:
        raise ValueError('Expected native21 startup receipt')
    raw=boot.read_bytes()
    if raw[:8]!=b'ANDROID!' or sha(raw)!=kernel.get('boot_sha256') or len(raw)!=kernel.get('boot_bytes'):
        raise ValueError('BOOT does not match startup receipt')
    compiler=run(['aarch64-linux-gnu-gcc','--version']).splitlines()[0]
    if compiler!=COMPILER:raise ValueError('Compiler mismatch')
    expected={'vmlinux':VMLINUX_SHA,'Module.symvers':SYMVERS_SHA,'vmlinux.symvers':SYMVERS_SHA}
    for name,digest in expected.items():
        if sha((out/name).read_bytes())!=digest:raise ValueError('Kernel21 link artifact changed: '+name)
    if (out/'include/config/kernel.release').read_text().strip()!=RELEASE:raise ValueError('Wrong kernel release')
    if f'"{VERSION}"' not in (out/'include/generated/utsversion.h').read_text():raise ValueError('Wrong kernel UTS version')
    files=sorted(p for p in (source/'fs/fuse').rglob('*') if p.is_file())
    files += [source/p for p in VFS]
    return {'schema':1,'model':'SM-G965N','kernel':kernel,'startup_sha256':sha(startup.read_bytes()),
            'tracked_kernel_headers_clean':True,
            'native_config_sha256':CONFIG_SHA,'compiler':compiler,'upstream_commit':HEAD,
            'link_artifacts':expected,'sources':{str(p.relative_to(source)):sha(p.read_bytes()) for p in files},
            'generated_headers':{name:sha((out/name).read_bytes()) for name in
                ['include/generated/autoconf.h','include/generated/utsrelease.h','include/generated/utsversion.h']}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['inspect','build'])
    for name in ['source','kernel-out','native-config','startup-receipt','boot','backup-manifest','output']:
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--build-out',type=Path)
    p.add_argument('--consent-host-build',action='store_true')
    a=p.parse_args()
    backup=json.loads(a.backup_manifest.read_text())
    parts=backup.get('partitions',[])
    entries={e['name']:e for e in parts}
    if backup.get('model')!='SM-G965N' or backup.get('complete') is not True or len(parts)!=9 or set(entries)!={'BOOT','DTB','DTBO','EFS','CPEFS','RADIO','MISC','RECOVERY','PARAM'}:
        raise ValueError('Expected verified nine-partition owner backup manifest')
    for e in entries.values():
        if not isinstance(e.get('bytes'),int) or e['bytes']<=0 or not re.fullmatch('[0-9a-f]{64}',e.get('sha256','')):
            raise ValueError('Invalid backup manifest metadata')
    before=inspect(a.source,a.kernel_out,a.native_config,a.startup_receipt,a.boot)
    if a.action=='inspect':
        print('Exact native21 FUSE inputs verified; no build/device changes.')
        return
    if not a.consent_host_build:raise SystemExit('Explicit --consent-host-build required')
    repo=Path(__file__).resolve().parents[2]
    if run(['git','-C',str(repo),'status','--porcelain','--','experiments/fuse']):
        raise ValueError('Commit the reviewed FUSE recipe before building')
    if not a.build_out or a.build_out.exists() or a.build_out.resolve().is_relative_to(a.kernel_out.resolve()):
        raise ValueError('Provide a new separate --build-out snapshot directory')
    if a.output.exists():raise ValueError('Output exists; preserve it and choose a new directory')
    os.umask(0o077);a.output.mkdir(parents=True,mode=0o700)
    shutil.copytree(a.kernel_out,a.build_out,symlinks=True)
    command=['make','-C',str(a.source),'O='+str(a.build_out),'ARCH=arm64',
             'CROSS_COMPILE=aarch64-linux-gnu-','-j2','fs/fuse/fuse.ko']
    before['command']=command
    (a.output/'inputs.json').write_text(json.dumps(before,indent=2)+'\n')
    environment=dict(os.environ)
    for name in ('KCFLAGS','KCPPFLAGS','CFLAGS_MODULE','AFLAGS_MODULE','MAKEFLAGS','MFLAGS',
                 'KBUILD_EXTRA_SYMBOLS','CC','HOSTCC','LD','LLVM','LLVM_IAS'):
        environment.pop(name,None)
    with (a.output/'build.log').open('w') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,env=environment)
    after=inspect(a.source,a.kernel_out,a.native_config,a.startup_receipt,a.boot)
    if any(before[k]!=after[k] for k in after):raise ValueError('Pinned inputs changed during module build; preserve evidence')
    for name,digest in before['link_artifacts'].items():
        if name!='Module.symvers' and sha((a.build_out/name).read_bytes())!=digest:
            raise ValueError('Snapshot kernel link artifact changed: '+name)
    if (a.build_out/'.config').read_bytes()!=a.native_config.read_bytes():raise ValueError('Snapshot config changed')
    old=set((a.kernel_out/'Module.symvers').read_text().splitlines())
    new=set((a.build_out/'Module.symvers').read_text().splitlines())
    if not old<=new or any(len(x.split())<3 or x.split()[2]!='fs/fuse/fuse' for x in new-old):
        raise ValueError('Unexpected symbol-table changes in isolated FUSE snapshot')
    data=(a.build_out/'fs/fuse/fuse.ko').read_bytes();info=module_info(data)
    (a.output/'fuse.ko').write_bytes(data)
    shutil.copyfile(a.startup_receipt,a.output/'startup.json')
    shutil.copyfile(a.backup_manifest,a.output/'backup.json')
    verifier=repo/'scripts/g965n/deploy-drivers.py'
    shutil.copyfile(verifier,a.output/'verify-kernel.py')
    for name in ['load-once.py','build-addon.py']:
        shutil.copyfile(Path(__file__).parent/name,a.output/name)
    before.update({'module':{'sha256':sha(data),'bytes':len(data),'modinfo':info},
                   'recipe_commit':run(['git','-C',str(repo),'rev-parse','HEAD']),
                   'verify_kernel_sha256':sha(verifier.read_bytes()),
                   'loader_sha256':sha((a.output/'load-once.py').read_bytes()),
                   'recipe_file_sha256':sha(Path(__file__).read_bytes()),
                   'backup_manifest_sha256':sha(a.backup_manifest.read_bytes()),
                   'build_symvers_sha256':sha((a.build_out/'Module.symvers').read_bytes()),
                   'insmod_command':['/usr/sbin/insmod','/proc/self/fd/VERIFIED_MODULE_FD']})
    (a.output/'receipt.json').write_text(json.dumps(before,indent=2)+'\n')
    print('FUSE add-on built and pinned; NOT loaded or tested on hardware.')


if __name__=='__main__':main()

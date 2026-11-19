#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded dependency-only owner RIL inspection; never calls its entry point."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import types

OWNER_RIL_SHA256="0b00c4cf3f29bdd2675d2afce715cb3803134d889236900305d623f7b22de383"
LIBRARY_PATH='/apex/com.android.runtime/lib64/bionic:/apex/com.android.runtime/lib64:/vendor/lib64:/system/lib64:/system/lib64/vndk-29:/system/lib64/vndk-sp-29'


def checked_module(path,digest):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
        raise ValueError('Helper must be an unlinked regular source file')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Helper source mismatch')
    module=types.ModuleType('verified_probe_helper');module.__file__=str(path)
    exec(compile(data,str(path),'exec'),module.__dict__)
    return module


def lab_relative(lab,data):
    if not lab.is_absolute() or '..' in lab.parts or not re.fullmatch('[a-z0-9-]{1,40}',lab.name):
        raise ValueError('Expected absolute named private lab')
    relative=lab.relative_to(data)
    if len(relative.parts)!=1:raise ValueError('Lab must be a direct private data child')
    return relative


def safe_records(output,phase):
    wanted={'readonly_self_test','ril_init_called'} if phase=='self-test' else {'library_loaded','ril_entry_present','ril_init_called'}
    records=[]
    for line in output.splitlines():
        try:value=json.loads(line)
        except ValueError:continue
        if isinstance(value,dict) and set(value).issubset(wanted) and 'ril_init_called' in value and all(type(v) is bool for v in value.values()):
            records.append(value)
    return records


def unit_command(runtime_root,relative,phase):
    return ['systemd-run','--unit=g965n-vprobe-'+relative.name+'-'+phase,'--wait','--pipe',
        '--property=RuntimeMaxSec=10s','--property=TimeoutStopSec=2s','--property=DevicePolicy=closed',
        '--property=NoNewPrivileges=yes','--property=ProtectSystem=strict','--property=ProtectKernelTunables=yes',
        '--property=ProtectKernelModules=yes','--property=PrivateNetwork=yes',
        '--property=CapabilityBoundingSet=CAP_SYS_CHROOT','--property=LimitCORE=0','--property=TasksMax=16',
        '--property=MemoryMax=256M','--property=UMask=0077','--setenv=LD_LIBRARY_PATH='+LIBRARY_PATH,
        '/usr/sbin/chroot',str(runtime_root),'/data/'+str(relative)+'/probe','--'+phase]


def private_write(path,data,mode=0o600):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(fd,'wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())


def run(args):
    if args.model!='SM-G965N':raise ValueError('Expected explicit SM-G965N')
    if os.geteuid()!=0 or not args.confirm_backup_verified or not args.consent_readonly_probe:
        raise ValueError('Root, verified backup and explicit read-only probe consent required')
    guard=checked_module(args.guard_helper,args.guard_helper_sha256)
    guard.validate(guard.trusted_json(args.receipt,args.receipt_sha256),
        guard.trusted_json(args.backup,args.backup_sha256),require_off=False)
    # The optional off check in the reused board guard concerns Wi-Fi P2P;
    # preserve that owner-confirmed feature. Check the modem independently.
    if Path('/sys/module/g965n_modem').exists():raise ValueError('Inspection requires modem module absent')
    runtime=checked_module(args.runtime_helper,args.runtime_helper_sha256)
    with runtime.shared_runtime_lock():
        runtime.assert_board()
        if not runtime.ROOT.is_mount():raise ValueError('Reviewed private runtime required')
        runtime.modem_bindings_absent()
        relative=lab_relative(args.private_lab,runtime.DATA)
        # Reuse only the reviewed build profile, never substitute other firmware.
        spec=importlib.util.spec_from_file_location('probe_build',Path(__file__).with_name('build-vendor-probe.py'))
        build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
        pins={'apex/com.android.runtime/lib64/bionic/'+n:h for n,h in build.PINS.items() if n!='linker64'}
        pins['apex/com.android.runtime/bin/linker64']=build.PINS['linker64']
        pins['vendor/lib64/libsec-ril.so']=OWNER_RIL_SHA256
        for name,digest in pins.items():
            path=runtime.ROOT/name
            if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise ValueError('Owner input mismatch: '+name)
        if args.binary.is_symlink() or not args.binary.is_file():raise ValueError('Expected probe binary')
        binary=args.binary.read_bytes()
        if hashlib.sha256(binary).hexdigest()!=args.binary_sha256:raise ValueError('Probe binary mismatch')
        lab=args.private_lab;boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if args.phase=='self-test':
            runtime.safe_components(lab.parent);lab.mkdir(mode=0o700)
            private_write(lab/'probe',binary,0o700)
        else:
            runtime.safe_components(lab)
            for p in (lab,lab/'probe',lab/'self-test.json'):
                st=p.lstat()
                if st.st_uid!=0 or st.st_mode&0o077:raise ValueError('Lab must stay root-private')
            prior=json.loads((lab/'self-test.json').read_text())
            if (prior['boot_id']!=boot or prior['binary_sha256']!=args.binary_sha256 or prior['returncode']!=0
                    or prior['records']!=[{'readonly_self_test':True,'ril_init_called':False}]):
                raise ValueError('Matching successful native self-test required before load')
            if hashlib.sha256((lab/'probe').read_bytes()).hexdigest()!=args.binary_sha256:
                raise ValueError('Staged probe changed')
        # Never overwrite evidence or repeat a same-phase unit silently.
        if (lab/(args.phase+'.json')).exists() or (lab/(args.phase+'-private.txt')).exists():
            raise ValueError('Preserve existing phase evidence; use a new lab')
        completed=subprocess.run(unit_command(runtime.ROOT,relative,args.phase),capture_output=True,text=True,timeout=20)
        private_write(lab/(args.phase+'-private.txt'),(completed.stdout+completed.stderr).encode())
        records=safe_records(completed.stdout,args.phase)
        expected=([{'readonly_self_test':True,'ril_init_called':False}] if args.phase=='self-test' else
                  [{'library_loaded':True,'ril_entry_present':True,'ril_init_called':False}])
        result={'boot_id':boot,'binary_sha256':args.binary_sha256,'returncode':completed.returncode,
                'records':records,'phase':args.phase,'verified':completed.returncode==0 and records==expected}
        private_write(lab/(args.phase+'.json'),(json.dumps(result,indent=2)+'\n').encode())
        return {k:result[k] for k in ('returncode','records','phase','verified')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',choices=['SM-G965N'],required=True)
    for name in ('receipt','backup','guard-helper','runtime-helper','binary'):
        parser.add_argument('--'+name,type=Path,required=True)
        parser.add_argument('--'+name+'-sha256',required=True)
    parser.add_argument('--private-lab',type=Path,required=True)
    parser.add_argument('--phase',choices=['self-test','inspect'],required=True)
    parser.add_argument('--confirm-backup-verified',action='store_true')
    parser.add_argument('--consent-readonly-probe',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    result=run(args);print(json.dumps(result));raise SystemExit(0 if result['verified'] else 1)


if __name__=='__main__':main()

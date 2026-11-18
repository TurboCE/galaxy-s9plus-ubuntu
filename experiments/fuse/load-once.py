#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded one-time FUSE insmod only. No services, firmware, flash, reboot or unload."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import types

PARTITIONS={'BOOT','DTB','DTBO','EFS','CPEFS','RADIO','MISC','RECOVERY','PARAM'}


def sha(data):return hashlib.sha256(data).hexdigest()


def safe_open(path):
    path=path.absolute()
    for parent in [*reversed(path.parents),path]:
        st=parent.lstat()
        if stat.S_ISLNK(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
            raise ValueError('Package must be root-owned and not group/world writable')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    st=os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1 or st.st_size>64*1024*1024:
        os.close(fd);raise ValueError('Expected bounded single-link ordinary file')
    return fd


def read_fd(fd):
    os.lseek(fd,0,os.SEEK_SET)
    chunks=[]
    while chunk:=os.read(fd,1024*1024):chunks.append(chunk)
    return b''.join(chunks)


def read(path):
    fd=safe_open(path)
    try:return read_fd(fd)
    finally:os.close(fd)


def validate_backup(data,expected):
    if sha(data)!=expected:raise ValueError('Backup manifest fingerprint mismatch')
    value=json.loads(data);parts=value.get('partitions',[])
    entries={p['name']:p for p in parts}
    if value.get('model')!='SM-G965N' or value.get('complete') is not True or len(parts)!=9 or set(entries)!=PARTITIONS:
        raise ValueError('Expected complete nine-partition owner backup manifest')
    if not all(type(p.get('bytes')) is int and p['bytes']>0 and re.fullmatch('[0-9a-f]{64}',p.get('sha256','')) for p in entries.values()):
        raise ValueError('Invalid backup metadata')


def checked_module(name,data,expected):
    if sha(data)!=expected:raise ValueError(name+' helper fingerprint mismatch')
    module=types.ModuleType(name)
    exec(compile(data,name,'exec'),module.__dict__)
    return module


def perform(package,expected_receipt,expected_boot,confirmed_backup,consent,model):
    if os.geteuid()!=0 or not consent or not confirmed_backup or model!='SM-G965N':
        raise ValueError('Root, explicit G965N consent and verified backup confirmation required')
    raw=read(package/'receipt.json')
    if sha(raw)!=expected_receipt:raise ValueError('Explicit package receipt fingerprint mismatch')
    receipt=json.loads(raw)
    if receipt.get('schema')!=1 or receipt.get('model')!=model or receipt['kernel'].get('boot_sha256')!=expected_boot:
        raise ValueError('Wrong package model/BOOT selection')
    if sha(read(Path(__file__)))!=receipt['loader_sha256']:raise ValueError('Loader changed')
    startup=read(package/'startup.json')
    if sha(startup)!=receipt['startup_sha256'] or json.loads(startup)!=receipt['kernel']:
        raise ValueError('Original startup receipt changed')
    validate_backup(read(package/'backup.json'),receipt['backup_manifest_sha256'])
    deploy=checked_module('kernel_verifier',read(package/'verify-kernel.py'),receipt['verify_kernel_sha256'])
    deploy.verify_kernel(receipt['kernel'])
    with gzip.open('/proc/config.gz','rb') as stream:config=stream.read(4*1024*1024+1)
    if len(config)>4*1024*1024 or sha(config)!=receipt['native_config_sha256']:
        raise ValueError('Running kernel config differs from exact module config')
    recipe=checked_module('fuse_recipe',read(package/'build-addon.py'),receipt['recipe_file_sha256'])
    if receipt['native_config_sha256']!=recipe.CONFIG_SHA:raise ValueError('Unreviewed native config')
    if Path('/sys/module/fuse').exists():raise ValueError('FUSE already loaded; no repeated insmod')
    fd=safe_open(package/'fuse.ko')
    try:
        data=read_fd(fd)
        if len(data)!=receipt['module']['bytes'] or sha(data)!=receipt['module']['sha256']:
            raise ValueError('Module fingerprint mismatch')
        if recipe.module_info(data)!=receipt['module']['modinfo']:raise ValueError('Module ABI metadata mismatch')
        # This FD remains open across insmod: no path-replacement hash/use race.
        subprocess.run(['/usr/sbin/insmod','/proc/self/fd/'+str(fd)],pass_fds=(fd,),check=True)
    finally:os.close(fd)
    print('One-time FUSE module load completed; portal operation still requires separate verification.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',type=Path,required=True)
    p.add_argument('--expected-receipt-sha256',required=True)
    p.add_argument('--expected-boot-sha256',required=True)
    p.add_argument('--model',choices=['SM-G965N'],required=True)
    p.add_argument('--confirm-backup-verified',action='store_true')
    p.add_argument('--consent-load-once',action='store_true')
    a=p.parse_args()
    a.package=a.package.absolute()
    # The package is root-private; hold an ordinary nofollow lock for this run.
    # An existing lock file is deliberately not truncated.
    for parent in [a.package,*a.package.parents]:
        st=parent.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=0 or st.st_mode&0o022:
            raise ValueError('Unsafe package directory')
    fd=os.open(a.package/'load.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        st=os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid!=0 or st.st_nlink!=1 or st.st_mode&0o077:
            raise ValueError('Unsafe load lock')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        perform(a.package,a.expected_receipt_sha256,a.expected_boot_sha256,
                a.confirm_backup_verified,a.consent_load_once,a.model)
    finally:os.close(fd)


if __name__=='__main__':main()

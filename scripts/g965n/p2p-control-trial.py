#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit BOOT/model/backup-guarded, bounded discovery-context trial.

No partition or firmware writes. A separately consented 90s reboot fallback
returns an opt-in-off kernel to its baseline if the trial cannot clean up.
Private output can contain wireless identifiers and must never be committed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

PARAM=Path('/sys/module/brcmfmac/parameters/g965n_legacy_p2pdev')
RECOVERY='g965n-p2p-control-recover'


def protected_parent(path):
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected absolute protected path')
    for parent in path.parents:
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o022:
            raise ValueError('Unprotected path ancestor')


def trusted_json(path, expected):
    protected_parent(path)
    if not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Invalid pin')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o077 or info.st_nlink!=1 or info.st_size>65536:
            raise ValueError('Unsafe private input')
        data=stream.read(65537)
    if len(data)>65536 or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Input pin mismatch')
    return json.loads(data)


def validate(receipt, backup):
    if (receipt.get('model')!='SM-G965N' or backup.get('model')!='SM-G965N' or
            not backup.get('complete') or not backup.get('bootloader','').startswith('G965N')):
        raise ValueError('Wrong model or incomplete backup')
    names={e['name'] for e in backup['partitions']}
    if names!={'BOOT','DTB','DTBO','EFS','CPEFS','RADIO','MISC','RECOVERY','PARAM'}:
        raise ValueError('Incomplete nine-partition backup')
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise ValueError('Wrong board')
    if (os.uname().version!=receipt['kernel_version'] or os.uname().release!=receipt['kernel_release']):
        raise ValueError('Wrong running kernel')
    size=receipt['boot_bytes']
    if type(size) is not int or not 8<=size<=57671680:raise ValueError('Invalid BOOT length')
    with open('/dev/sda10','rb') as stream:
        if hashlib.sha256(stream.read(size)).hexdigest()!=receipt['boot_sha256']:
            raise ValueError('Actual BOOT differs')
    if PARAM.read_text().strip()!='N':raise ValueError('Trial requires opt-in-off baseline')


def devices(text):
    result={};entry={}
    def flush():
        if 'wdev' in entry:result[entry['wdev']]=dict(entry)
    for line in text.splitlines():
        line=line.strip()
        if line.startswith(('Interface ','Unnamed/','phy#')):
            flush();entry={}
        match=re.fullmatch(r'wdev (0x[0-9a-fA-F]+)',line)
        if match:entry['wdev']=match[1].lower()
        if line.startswith('type '):entry['type']=line[5:]
    flush();return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',choices=['SM-G965N'],required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--receipt-sha256',required=True)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--backup-sha256',required=True)
    parser.add_argument('--log',type=Path,required=True)
    parser.add_argument('--confirm-backup-verified',action='store_true')
    parser.add_argument('--consent-p2p-control-trial',action='store_true')
    parser.add_argument('--consent-reboot-fallback',action='store_true')
    parser.add_argument('--scan',action='store_true',help='Also request one-channel DIRECT- scan; not peer traffic proof')
    parser.add_argument('--cycles',type=int,choices=[1,2,3],default=2)
    args=parser.parse_args()
    if os.geteuid()!=0 or not all([args.confirm_backup_verified,args.consent_p2p_control_trial,args.consent_reboot_fallback]):
        parser.error('Root, verified backup and explicit trial/reboot consent required')
    validate(trusted_json(args.receipt,args.receipt_sha256),trusted_json(args.backup,args.backup_sha256))
    protected_parent(args.log)
    if stat.S_IMODE(args.log.parent.stat().st_mode)!=0o700:raise ValueError('Log parent must be private0700')
    fd=os.open(args.log,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    records=[];summary=[];owned=None;armed=False;success=False
    def run(command,timeout=8,check=True):
        result=subprocess.run(command,text=True,capture_output=True,timeout=timeout)
        records.append({'command':command,'returncode':result.returncode,'stdout':result.stdout[:131072],'stderr':result.stderr[:16384]})
        if check and result.returncode:raise RuntimeError('Trial operation failed; details kept privately')
        return result.stdout
    def inventory():return devices(run(['iw','dev']))
    def traffic():
        code=run(['curl','--interface','wlp1s0','--connect-timeout','3','--max-time','8','-fsSL','-o','/dev/null','-w','%{http_code}','https://connectivity-check.ubuntu.com/'],timeout=10)
        if code not in ('200','204'):raise RuntimeError('Wi-Fi HTTPS probe not successful')
        return code
    try:
        baseline=inventory()
        if any(e.get('type')=='P2P-device' for e in baseline.values()):raise ValueError('Existing P2P device; trial refuses ownership')
        primary=json.loads(run(['ip','-j','link','show','dev','wlp1s0']))[0]
        traffic()
        # These checks and logging all precede the opt-in write.
        result=subprocess.run(['systemctl','is-active',RECOVERY+'.timer'],capture_output=True,text=True)
        if result.returncode==0:raise ValueError('Existing recovery timer; no overlapping trial')
        run(['systemd-run','--unit='+RECOVERY,'--on-active=90s','/usr/bin/systemctl','reboot'])
        armed=True;start=time.monotonic();PARAM.write_text('Y\n')
        for cycle in range(args.cycles):
            if time.monotonic()-start>60:raise RuntimeError('Bounded trial time exhausted')
            before=inventory()
            run(['iw','phy','phy0','interface','add','g965n-p2ptest','type','__p2pdev'])
            after=inventory();created=set(after)-set(before)
            if len(created)!=1:raise RuntimeError('Ambiguous context ownership; no guessed delete')
            owned=created.pop()
            if after[owned].get('type')!='P2P-device':raise RuntimeError('Unexpected created interface type')
            run(['iw','wdev',owned,'p2p','start'])
            scan=None
            # P2P scans require the listen-channel attribute; XX/0x04 with
            # global operating class81/channel1 does not change the regdomain.
            if args.scan:scan=run(['iw','wdev',owned,'scan','ies','dd:0c:50:6f:9a:09:06:05:00:58:58:04:51:01','freq','2412','ssid','DIRECT-'],timeout=10)
            run(['iw','wdev',owned,'p2p','stop'])
            run(['iw','wdev',owned,'del'])
            if owned in inventory():raise RuntimeError('Owned context survived delete')
            owned=None
            link=json.loads(run(['ip','-j','link','show','dev','wlp1s0']))[0]
            if (link['ifindex'],link['address'])!=(primary['ifindex'],primary['address']):raise RuntimeError('Primary interface changed')
            summary.append({'cycle':cycle+1,'create_start_stop_delete':True,'scan_completed':scan is not None,'wifi_https':traffic()})
        PARAM.write_text('N\n')
        run(['systemctl','stop',RECOVERY+'.timer']);success=True
    finally:
        if owned is not None:
            try:
                run(['iw','wdev',owned,'p2p','stop'],check=False)
                run(['iw','wdev',owned,'del'],check=False)
            except (OSError,subprocess.SubprocessError):pass
        if armed:PARAM.write_text('N\n')
        with os.fdopen(fd,'w') as stream:
            json.dump({'success':success,'summary':summary,'records':records,'recovery_left_armed':armed and not success},stream)
        print(json.dumps({'success':success,'summary':summary,'recovery_left_armed':armed and not success}),flush=True)


if __name__=='__main__':main()

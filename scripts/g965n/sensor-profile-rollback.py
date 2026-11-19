#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit exact-BOOT rollback of private sensor config for an unattended trial.

No installer, flashing, module loading or hardware reset commands. The caller
must prepare/pin private baseline snapshots and explicitly authorize a reboot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

PROFILE = Path('/var/lib/g965n-sensors/profile.json')
UNIT = Path('/etc/systemd/system/g965n-sensors.service')
TIMER = 'g965n-ssi-trial-rollback.timer'


def trusted(path, limit=1024*1024):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected absolute private snapshot')
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Snapshot ancestor not protected by root')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or
                info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > limit):
            raise ValueError('Unsafe private snapshot metadata')
        data = stream.read(limit+1)
    if len(data) > limit:
        raise ValueError('Snapshot exceeds bound')
    return data


def pinned(entry):
    data = trusted(entry['path'])
    if hashlib.sha256(data).hexdigest() != entry.get('sha256') or len(data) != entry.get('bytes'):
        raise ValueError('Private baseline checksum differs')
    return data


def verify_boot(value):
    size, sha = value['boot_bytes'], value['boot_sha256']
    if type(size) is not int or not 8 <= size <= 57671680 or not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('Invalid BOOT bounds')
    h = hashlib.sha256()
    with open('/dev/sda10', 'rb') as stream:
        while size:
            data = stream.read(min(size, 1024*1024))
            if not data:
                raise ValueError('Short actual BOOT')
            size -= len(data)
            h.update(data)
    if h.hexdigest() != sha or os.uname().version != value['kernel_version']:
        raise ValueError('BOOT/kernel changed; no guessed rollback')


def baseline(value):
    if value.get('schema') != 1 or value.get('model') != 'SM-G965N':
        raise ValueError('Wrong rollback model/schema')
    profile, unit = pinned(value['profile']), pinned(value['unit'])
    p = json.loads(profile)
    if (p.get('model') != 'SM-G965N' or p.get('expected_boot_sha256') != value['boot_sha256'] or
            p.get('transport', {}).get('strict_tx_ack', False) is not False):
        raise ValueError('Baseline must disable the trial on this exact BOOT')
    profile_sha = hashlib.sha256(profile).hexdigest()
    if (unit.count(b'ExecStart=') != 1 or
            ('--profile '+str(PROFILE)+' ').encode() not in unit or
            ('--profile-sha256 '+profile_sha+' ').encode() not in unit):
        raise ValueError('Baseline unit does not pin baseline profile')
    return profile, unit, profile_sha


def atomic_write(path, data, mode):
    if path.is_symlink():
        raise ValueError('Refusing symlink rollback target')
    fd, temporary = tempfile.mkstemp(prefix='.g965n-rollback-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restore(value, reboot=False):
    profile, unit, sha = baseline(value)
    verify_boot(value)  # All checks precede stopping or changing anything.
    try:
        subprocess.run(['systemctl', 'stop', 'g965n-sensors.service'], check=True, timeout=220)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        if not reboot:
            raise
        # Known baseline will only take effect after the explicit reboot.
        print('Sensor stop incomplete; restoring pinned baseline for reboot', flush=True)
    atomic_write(PROFILE, profile, 0o600)
    atomic_write(UNIT, unit, 0o644)
    atomic_write(PROFILE.with_name('profile.sha256'), (sha+'\n').encode(), 0o600)
    subprocess.run(['systemctl', 'disable', TIMER], check=True, timeout=15)
    subprocess.run(['systemctl', 'daemon-reload'], check=True, timeout=15)
    print('Pinned non-trial sensor configuration restored', flush=True)
    if reboot:
        subprocess.run(['systemctl', 'reboot'], check=True, timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--state-sha256', required=True)
    parser.add_argument('--model', choices=['SM-G965N'], required=True)
    parser.add_argument('--confirm-backup-verified', action='store_true')
    parser.add_argument('--consent-profile-rollback', action='store_true')
    parser.add_argument('--reboot', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0 or not args.confirm_backup_verified or not args.consent_profile_rollback:
        parser.error('Root, verified backup and explicit rollback consent required')
    data = trusted(args.state, 16384)
    if hashlib.sha256(data).hexdigest() != args.state_sha256:
        raise ValueError('Rollback state differs')
    restore(json.loads(data), args.reboot)


if __name__ == '__main__':
    main()

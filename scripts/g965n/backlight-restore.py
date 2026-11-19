#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Private exact-BOOT maximum-brightness rollback for a manual backlight trial.

No installer, unit creation or automatic trial. Stage as protected root-owned
source, save a private state, then arm an independent systemd timer before
changing brightness. Recovery can deliberately leave ambient dimming disabled.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

BACKLIGHT = Path('/sys/class/backlight/g965n-panel-aor')


def verify_boot(sha, size):
    if not re.fullmatch('[0-9a-f]{64}', sha) or type(size) is not int or not 8 <= size <= 57671680:
        raise ValueError('Invalid exact BOOT bounds')
    h = hashlib.sha256()
    with open('/dev/sda10', 'rb') as stream:
        left = size
        while left:
            chunk = stream.read(min(left, 1024 * 1024))
            if not chunk:
                raise ValueError('Short actual BOOT read')
            h.update(chunk)
            left -= len(chunk)
    if h.hexdigest() != sha:
        raise ValueError('Running device BOOT differs; no brightness change')


def state_parent(path):
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected absolute private state path')
    for parent in (path.parent, *path.parent.parents):
        info = parent.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or
                info.st_mode & (0o077 if parent == path.parent else 0o022)):
            raise ValueError('State path is not protected by root')


def load_state(path, expected):
    state_parent(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or
                stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size > 4096):
            raise ValueError('Unsafe saved state')
        data = stream.read(4097)
    if len(data) > 4096 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Saved state differs')
    value = json.loads(data)
    if (value.get('schema') != 1 or value.get('model') != 'SM-G965N' or
            type(value.get('ambient_enabled')) is not bool or value.get('maximum') != 16):
        raise ValueError('Wrong backlight rollback state')
    return value


def desktop_settings(*args):
    return subprocess.check_output(['sudo', '-u', 'ubuntu', 'env',
        'XDG_RUNTIME_DIR=/run/user/1000', 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus',
        'gsettings', *args], timeout=10).decode().strip()


def restore(value, keep_disabled):
    verify_boot(value['boot_sha256'], value['boot_bytes'])
    if BACKLIGHT.joinpath('max_brightness').read_text().strip() != '16':
        raise ValueError('Backlight range differs; no guessed restore')
    desktop_settings('set', 'org.gnome.settings-daemon.plugins.power', 'ambient-enabled', 'false')
    BACKLIGHT.joinpath('brightness').write_text('16\n')
    if BACKLIGHT.joinpath('actual_brightness').read_text().strip() != '16':
        raise RuntimeError('Maximum brightness transaction was not confirmed')
    if not keep_disabled:
        desktop_settings('set', 'org.gnome.settings-daemon.plugins.power', 'ambient-enabled',
                         'true' if value['ambient_enabled'] else 'false')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['save', 'restore'])
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--state-sha256')
    parser.add_argument('--model', choices=['SM-G965N'])
    parser.add_argument('--boot-sha256')
    parser.add_argument('--boot-bytes', type=int)
    parser.add_argument('--confirm-backup-verified', action='store_true')
    parser.add_argument('--consent-brightness-trial', action='store_true')
    parser.add_argument('--keep-ambient-disabled', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Root with explicit private trial state required')
    if args.action == 'save':
        if not args.model or not args.confirm_backup_verified or not args.consent_brightness_trial:
            parser.error('Explicit G965N model, verified backup and brightness-trial consent required')
        state_parent(args.state)
        verify_boot(args.boot_sha256 or '', args.boot_bytes)
        maximum = int(BACKLIGHT.joinpath('max_brightness').read_text())
        if maximum != 16:
            raise ValueError('Unexpected backlight range')
        ambient = desktop_settings('get', 'org.gnome.settings-daemon.plugins.power', 'ambient-enabled')
        if ambient not in ('true', 'false'):
            raise ValueError('Unknown original ambient setting')
        value = {'schema': 1, 'model': args.model, 'boot_sha256': args.boot_sha256,
                 'boot_bytes': args.boot_bytes, 'maximum': maximum, 'ambient_enabled': ambient == 'true'}
        data = (json.dumps(value) + '\n').encode()
        fd = os.open(args.state, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        print(hashlib.sha256(data).hexdigest())
    else:
        restore(load_state(args.state, args.state_sha256), args.keep_ambient_disabled)
        print('Maximum brightness command confirmed; ambient policy restored as requested')


if __name__ == '__main__':
    main()

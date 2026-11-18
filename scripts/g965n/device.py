#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only SM-G965N recovery inspection and byte/hash-verified backups."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

BYNAME = '/dev/block/platform/11120000.ufs/by-name/'
PARTITIONS = {'BOOT': 'sda10', 'DTB': 'sda8', 'DTBO': 'sda9', 'EFS': 'sda3',
              'CPEFS': 'sdd1', 'RADIO': 'sda12', 'MISC': 'sda15',
              'RECOVERY': 'sda11', 'PARAM': 'sda4'}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    return h.hexdigest()


class Device:
    def __init__(self, adb, serial):
        self.command = [adb, '-s', serial]

    def call(self, *args, **kwargs):
        return subprocess.run(self.command + list(args), check=True, timeout=300, **kwargs)

    def shell(self, command):
        return self.call('shell', command, capture_output=True).stdout.decode().strip()

    def inspect(self):
        state = self.call('get-state', capture_output=True).stdout.decode().strip()
        require(state == 'recovery', 'Phone must be in TWRP recovery.')
        loader = self.shell('getprop ro.bootloader')
        require(loader.startswith('G965N'), 'Bootloader does not identify as SM-G965N.')
        require(self.shell('getprop ro.product.device') == 'star2lte', 'Wrong recovery device.')
        version = self.shell('getprop ro.twrp.version')
        require(bool(version), 'TWRP is not running.')
        require(self.shell('id -u') == '0', 'Recovery is not root.')
        for name, node in PARTITIONS.items():
            require(self.shell('readlink -f ' + BYNAME + name) == '/dev/block/' + node,
                    'Unexpected partition mapping: ' + name)
        return {'model': 'SM-G965N', 'bootloader': loader, 'twrp': version}

    def backup(self, directory):
        info = self.inspect()
        directory = Path(directory)
        require(not directory.exists(), 'Backup directory already exists; choose a new one.')
        os.umask(0o077)
        directory.mkdir(parents=True, mode=0o700)
        info.update(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    recovery_note='RECOVERY is TWRP, not the original stock recovery.', partitions=[])
        for name in PARTITIONS:
            device = BYNAME + name
            size = int(self.shell('blockdev --getsize64 ' + device))
            require(0 < size < 300 * (1 << 20), 'Unexpected size: ' + name)
            target = directory / (name + '.img')
            print('Reading', name, size, flush=True)
            with target.open('wb') as stream:
                # exec-out can merge remote stderr with stdout. Never let dd's
                # byte-count report corrupt the binary backup.
                self.call('exec-out', 'dd if=' + device + ' bs=1048576 2>/dev/null',
                          stdout=stream, stderr=subprocess.PIPE)
            require(target.stat().st_size == size, 'Backup byte count mismatch: ' + name)
            expected = self.shell('sha256sum ' + device).split()[0]
            require(digest(target) == expected, 'Backup SHA256 mismatch: ' + name)
            info['partitions'].append({'name': name, 'bytes': size, 'sha256': expected})
            (directory / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
            print('Verified', name, flush=True)
        info['complete'] = True
        (directory / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
        return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--serial', required=True)
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    device = Device(args.adb, args.serial)
    info = device.backup(args.backup) if args.backup else device.inspect()
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()

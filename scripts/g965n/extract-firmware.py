#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Extract Wi-Fi firmware from your G965N's VENDOR, mounted read-only without journal replay."""
import argparse
import os
from pathlib import Path
import subprocess

from device import Device, digest, require
from firmware import FILES, stage


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', default='adb')
    p.add_argument('--serial', required=True)
    p.add_argument('--out', type=Path, default=Path('.local/stock-firmware'))
    args = p.parse_args()
    os.umask(0o077)
    device = Device(args.adb, args.serial)
    device.inspect()
    mount = '/tmp/g965n-vendor-export'
    require(mount not in device.shell('cat /proc/mounts'), 'Export mount already exists.')
    require(device.shell('readlink -f /dev/block/platform/11120000.ufs/by-name/VENDOR')
            == '/dev/block/sda19', 'Unexpected VENDOR partition mapping.')
    device.shell('mkdir -p ' + mount)
    device.shell('mount -t ext4 -o ro,noload /dev/block/sda19 ' + mount)
    try:
        require(not args.out.exists(), 'Output already exists; choose a fresh --out directory.')
        args.out.mkdir(parents=True, mode=0o700)
        for name in FILES:
            remote = None
            for folder in ('firmware', 'etc/wifi'):
                candidate = mount + '/' + folder + '/' + name
                try:
                    device.shell('test -f ' + candidate)
                    remote = candidate
                    break
                except subprocess.CalledProcessError:
                    pass
            require(remote is not None, 'Stock firmware file not found: ' + name)
            local = args.out / name
            device.call('pull', remote, str(local))
            require(digest(local) == device.shell('sha256sum ' + remote).split()[0],
                    'Firmware transfer checksum mismatch: ' + name)
    finally:
        device.shell('umount ' + mount)
    stage(args.out)
    print('Own-device firmware extracted, verified and staged locally; do not publish it.')


if __name__ == '__main__':
    main()

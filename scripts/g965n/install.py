#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check a G965N and its backup before delegating to the original verified-write tools."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from device import Device, PARTITIONS, digest, require

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', default='adb')
    p.add_argument('--serial', required=True)
    p.add_argument('--backup', type=Path, required=True)
    p.add_argument('--rootfs', type=Path, required=True)
    p.add_argument('--boot', type=Path, required=True)
    p.add_argument('--erase-userdata-experimental-g965n', action='store_true')
    args = p.parse_args()
    require(args.erase_userdata_experimental_g965n,
            'G965N Ubuntu boot is not validated. Explicit experimental/USERDATA erase consent is required.')
    device = Device(args.adb, args.serial)
    current = device.inspect()
    manifest = json.loads((args.backup / 'manifest.json').read_text())
    require(manifest.get('complete') is True, 'Backup is incomplete.')
    require(manifest.get('bootloader') == current['bootloader'], 'Backup firmware mismatch.')
    entries = {entry['name']: entry for entry in manifest['partitions']}
    require(set(entries) == set(PARTITIONS), 'Missing partition backups.')
    for name, entry in entries.items():
        file = args.backup / (name + '.img')
        require(file.stat().st_size == entry['bytes'] and digest(file) == entry['sha256'],
                'Invalid backup: ' + name)
        # EFS must also match this handset, not another phone of the same model.
        if name in ('EFS', 'CPEFS'):
            require(device.shell('sha256sum ' + '/dev/block/platform/11120000.ufs/by-name/' + name).split()[0]
                    == entry['sha256'], 'Backup belongs to a different or changed phone: ' + name)
    for path in (args.boot, args.rootfs):
        require(path.resolve().is_relative_to((ROOT / 'dist').resolve()), 'Images must be inside dist/.')
        require(path.is_file(), 'Missing image: ' + str(path))
    with args.boot.open('rb') as stream:
        require(stream.read(8) == b'ANDROID!', 'Invalid boot image header.')
    with args.rootfs.open('rb') as stream:
        stream.seek(1024 + 56)
        require(stream.read(2) == b'\x53\xef', 'Root filesystem is not ext4.')
    environment = dict(os.environ, S9PLUS_ADB=args.adb, S9PLUS_SERIAL=args.serial)
    print('Experimental install: replacing USERDATA, then BOOT; RECOVERY is preserved.', flush=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/flash/flash_s9plus_rootfs_adb.py'),
                    str(args.rootfs.resolve())], env=environment, check=True)
    subprocess.run([sys.executable, str(ROOT / 'scripts/flash/flash_s9plus_boot_adb.py'),
                    str(args.boot.resolve())], env=environment, check=True)


if __name__ == '__main__':
    main()

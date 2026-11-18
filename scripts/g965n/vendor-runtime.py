#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare an isolated filesystem for the owner's stock vendor programs.

Run manually as root on native Ubuntu. Does not start Android, lhd or cbd.
SYSTEM/VENDOR are read-only with no journal replay; identity/radio partitions
are never mounted or exposed as block devices inside this runtime.
"""
import argparse
import fcntl
import os
from pathlib import Path
import stat
import subprocess

BASE = Path('/run/g965n-vendor-runtime')
ROOT = BASE / 'root'
DATA = Path('/var/lib/g965n-vendor-runtime/data')


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def mount(source, target, *options):
    target.mkdir(parents=True, exist_ok=True)
    run('mount', *options, source, target)


def prepare():
    if os.path.ismount(ROOT):
        raise RuntimeError('Runtime already mounted; reuse it or tear it down first')
    for partition, node in [('SYSTEM', '/dev/sda18'), ('VENDOR', '/dev/sda19')]:
        label = subprocess.check_output(['lsblk', '-n', '-o', 'PARTLABEL', node], text=True).strip()
        if label != partition:
            raise RuntimeError('Unexpected partition mapping')
        mount(node, BASE / partition, '-t', 'ext4', '-o', 'ro,noload')
    system = BASE / 'SYSTEM/system'
    vendor = BASE / 'VENDOR'
    if not (system / 'bin').is_dir():
        raise RuntimeError('Unexpected stock SYSTEM layout')
    mount('tmpfs', ROOT, '-t', 'tmpfs', '-o', 'mode=700,size=4m')
    for name in ('tmp', 'dev', 'proc', 'sys', 'data', 'apex/com.android.runtime'):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    mount(system, ROOT / 'system', '--bind')
    run('mount', '-o', 'remount,bind,ro', ROOT / 'system')
    mount(vendor, ROOT / 'vendor', '--bind')
    run('mount', '-o', 'remount,bind,ro', ROOT / 'vendor')
    apex = system / 'apex/com.android.runtime.release'
    if not apex.is_dir():
        raise RuntimeError('Stock Android runtime APEX missing')
    mount(apex, ROOT / 'apex/com.android.runtime', '--bind')
    run('mount', '-o', 'remount,bind,ro', ROOT / 'apex/com.android.runtime')
    mount('proc', ROOT / 'proc', '-t', 'proc')
    mount('/sys', ROOT / 'sys', '--bind')
    for name in ('vendor/gps', 'system/gps', 'log'):
        (DATA / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    mount(DATA, ROOT / 'data', '--bind')
    # Individual character devices only: never bind the host's entire /dev.
    selected = ['null', 'zero', 'random', 'urandom', 'ttyBCM', 'bbd_control', 'bbd_sensor', 'bbd_patch']
    selected += [p.name for p in Path('/dev').glob('umts_*')]
    for name in selected:
        source = Path('/dev') / name
        if source.exists():
            st = source.stat()
            if not stat.S_ISCHR(st.st_mode):
                raise RuntimeError('Expected character device: ' + name)
            os.mknod(ROOT / 'dev' / name, stat.S_IFCHR | 0o600, st.st_rdev)
    (ROOT / 'bin').symlink_to('system/bin')
    (ROOT / 'etc').symlink_to('system/etc')
    print('Owner vendor runtime prepared; no daemon started; no identity block devices exposed.')


def teardown():
    # Refuse busy mounts; never hide running processes with a lazy unmount.
    if os.path.ismount(ROOT):
        run('umount', '-R', ROOT)
    for name in ('VENDOR', 'SYSTEM'):
        target = BASE / name
        if os.path.ismount(target):
            run('umount', target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('up', 'down'))
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run as root on the handset')
    compatibles = Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0')
    if b'samsung,star2lte' not in compatibles:
        raise SystemExit('Expected star2lte')
    with open('/run/g965n-vendor-runtime.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'down':
            teardown()
        else:
            if os.path.ismount(ROOT):
                raise SystemExit('Runtime already mounted; existing runtime preserved')
            try:
                prepare()
            except BaseException:
                teardown()
                raise


if __name__ == '__main__':
    main()

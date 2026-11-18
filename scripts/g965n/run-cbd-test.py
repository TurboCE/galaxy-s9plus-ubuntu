#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded manual test of the owner's cbd, with private NV and device filtering.

Requires vendor-runtime.py stage-modem first. No automatic retries/autostart.
The stock arguments come from this G965N's VENDOR/etc/init/init.baseband.rc.
"""
import argparse
import os
from pathlib import Path
import stat
from gi.repository import Gio, GLib

ROOT = Path('/run/g965n-vendor-runtime/root')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-private-nv-copy', action='store_true', required=True)
    parser.add_argument('--seconds', type=int, choices=range(10, 121), default=60)
    parser.add_argument('--trace', action='store_true', help='Private host strace around chroot/exec')
    args = parser.parse_args()
    if os.geteuid() != 0 or not os.path.ismount(ROOT):
        raise SystemExit('Expected root and the prepared private vendor runtime')
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected star2lte')
    radio = ROOT / 'dev/block/platform/11120000.ufs/by-name/RADIO'
    if not stat.S_ISREG(radio.stat().st_mode) or radio.stat().st_size != 52428800:
        raise SystemExit('Expected a private regular RADIO copy, never a block device')
    for name in ('efs', 'cpefs'):
        if not os.path.ismount(ROOT / 'mnt/vendor' / name):
            raise SystemExit('Missing private NV working mount')
    allow = []
    for path in Path('/dev').glob('umts_*'):
        if not stat.S_ISCHR(path.stat().st_mode):
            raise SystemExit('Unexpected modem device type')
        allow.append((str(path), 'rw'))
    if not any(p.endswith('/umts_boot0') for p, _ in allow):
        raise SystemExit('Modem boot control node missing')
    executable = '/vendor/bin/cbd'
    command = [executable, '-d', '-tss310', '-bm', '-mm', '-P',
               'platform/11120000.ufs/by-name/RADIO', '-n', '/mnt/vendor/efs']
    properties = [
        ('Description', GLib.Variant('s', 'Bounded G965N own-vendor modem boot test')),
        ('DevicePolicy', GLib.Variant('s', 'closed')),
        # RootDirectory otherwise overlays API filesystems and hides the
        # deliberately staged modem nodes/log socket from this runtime.
        ('MountAPIVFS', GLib.Variant('b', False)),
        ('DeviceAllow', GLib.Variant('a(ss)', allow)),
        ('NoNewPrivileges', GLib.Variant('b', True)),
        ('UMask', GLib.Variant('u', 0o077)),
        ('RuntimeMaxUSec', GLib.Variant('t', args.seconds * 1000000)),
        ('Restart', GLib.Variant('s', 'no')),
    ]
    # Use the already prepared mounts directly. A systemd RootDirectory launch
    # also reconfigures API filesystems; this runtime deliberately stages /dev.
    command = ['/usr/sbin/chroot', str(ROOT)] + command
    if args.trace:
        command = ['/usr/bin/strace', '-f', '-s', '100', '-o',
                   '/var/lib/g965n-vendor-runtime/cbd-start.strace'] + command
    executable = command[0]
    properties.append(('ExecStart', GLib.Variant('a(sasb)', [(executable, command, False)])))
    bus = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SYSTEM, 0, None,
        'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', None)
    bus.call_sync('StartTransientUnit', GLib.Variant('(ssa(sv)a(sa(sv)))', (
        'g965n-cbd-test.service', 'fail', properties, [])), 0, 5000, None)
    print('g965n-cbd-test.service started with closed device policy; inspect private logs.')


if __name__ == '__main__':
    main()

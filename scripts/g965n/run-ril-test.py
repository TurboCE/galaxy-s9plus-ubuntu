#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Start a bounded IPC/RFS test, then the own-vendor modem boot daemon.

Only for the manually reviewed G965N experimental driver. Powers off this
modem first; does not reboot the phone or write a partition. Uses the OFF
ioctl defined in the GPL vendor modem_prj.h. Never use during a live call.
"""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import re
from gi.repository import Gio, GLib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-directory', type=Path, required=True)
    parser.add_argument('--apn', required=True)
    parser.add_argument('--confirm-private-nv-copy', action='store_true', required=True)
    parser.add_argument('--seconds', type=int, choices=range(30, 121), default=90)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9.-]{1,100}', args.apn):
        raise SystemExit('Invalid APN')
    if os.geteuid() != 0 or b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected root on star2lte')
    for name in ('ril-lab.py', 'rfs-copy.py'):
        if not (args.lab_directory / name).is_file():
            raise SystemExit('Missing reviewed lab source: ' + name)
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'g965n-cbd-test']).returncode == 0:
        raise SystemExit('Stop the previous bounded cbd test first')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'g965n-ril-lab-test']).returncode == 0:
        raise SystemExit('Stop the previous bounded RIL test first')
    # No active modem-control daemon. This affects only the test handset CP.
    with open('/dev/umts_boot0', 'rb', buffering=0) as boot:
        fcntl.ioctl(boot.fileno(), 0x6f20, 0)  # _IO('o',0x20), IOCTL_MODEM_OFF
    command = ['/usr/bin/python3', str((args.lab_directory / 'ril-lab.py').resolve()),
               '--seconds', str(args.seconds), '--configure-radio', '--apn', args.apn]
    properties = [
        ('Description', GLib.Variant('s', 'Bounded G965N private-copy IPC/RFS lab')),
        ('DevicePolicy', GLib.Variant('s', 'closed')),
        ('DeviceAllow', GLib.Variant('a(ss)', [('/dev/' + p, 'rw') for p in ('umts_ipc0', 'umts_rfs0', 'umts_router')])),
        ('UMask', GLib.Variant('u', 0o077)),
        ('NoNewPrivileges', GLib.Variant('b', True)),
        ('RuntimeMaxUSec', GLib.Variant('t', (args.seconds + 5) * 1000000)),
        ('Restart', GLib.Variant('s', 'no')),
        ('ExecStart', GLib.Variant('a(sasb)', [(command[0], command, False)])),
    ]
    bus = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SYSTEM, 0, None,
        'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', None)
    bus.call_sync('StartTransientUnit', GLib.Variant('(ssa(sv)a(sa(sv)))', (
        'g965n-ril-lab-test.service', 'fail', properties, [])), 0, 5000, None)
    if subprocess.run(['systemctl', 'is-failed', '--quiet', 'g965n-cbd-test']).returncode == 0:
        subprocess.run(['systemctl', 'reset-failed', 'g965n-cbd-test'], check=True)
    subprocess.run([sys.executable, str(Path(__file__).with_name('run-cbd-test.py')),
                    '--confirm-private-nv-copy', '--seconds', '120'], check=True)
    print('Bounded RIL/RFS and cbd tests started; read private journal, not a success claim.')


if __name__ == '__main__':
    main()

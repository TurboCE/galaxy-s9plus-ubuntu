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
import importlib.util


def load_runtime(helper):
    if helper.is_symlink() or not helper.is_file():
        raise RuntimeError('Missing reviewed vendor-runtime helper')
    spec = importlib.util.spec_from_file_location('g965n_runtime_preflight', helper)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def verify_private_runtime(helper, runtime=None):
    """Caller holds shared runtime lease; no MODEM_OFF before all checks pass."""
    runtime = runtime if runtime is not None else load_runtime(helper)
    runtime.assert_board()
    runtime.validate_modem_state(runtime.read_provenance())
    runtime.verify_private_bindings()
    return runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-directory', type=Path, required=True)
    parser.add_argument('--apn', required=True)
    parser.add_argument('--runtime-helper', type=Path, default=Path(__file__).with_name('vendor-runtime.py'))
    parser.add_argument('--confirm-private-nv-copy', action='store_true', required=True)
    parser.add_argument('--seconds', type=int, choices=range(30, 121), default=90)
    parser.add_argument('--activate-pdp-s9', action='store_true')
    parser.add_argument('--confirm-reviewed-s9-pdp-layout', action='store_true')
    parser.add_argument('--pdp-cid', type=int, choices=(1,), default=1)
    parser.add_argument('--pdp-seconds', type=int, choices=range(10,61), default=30)
    args = parser.parse_args()
    if bool(getattr(args, 'activate_pdp_s9', False)) != bool(getattr(args, 'confirm_reviewed_s9_pdp_layout', False)):
        raise SystemExit('S9 PDP requires explicit opt-in and reviewed-layout confirmation')
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
    runtime = load_runtime(args.runtime_helper)
    with runtime.shared_runtime_lock():
        verify_private_runtime(args.runtime_helper, runtime)
        from gi.repository import Gio, GLib
        # No active modem-control daemon. This affects only the test handset CP.
        with open('/dev/umts_boot0', 'rb', buffering=0) as boot:
            fcntl.ioctl(boot.fileno(), 0x6f20, 0)  # _IO('o',0x20), IOCTL_MODEM_OFF
        command = ['/usr/bin/python3', str((args.lab_directory / 'ril-lab.py').resolve()),
                   '--seconds', str(args.seconds), '--configure-radio', '--apn', args.apn,
                   '--runtime-helper', str(args.runtime_helper.resolve()),
                   '--expected-receipt-sha256', runtime.launch_receipt_digest()]
        if args.activate_pdp_s9:
            command += ['--activate-pdp-s9', '--confirm-reviewed-s9-pdp-layout',
                        '--pdp-cid', str(args.pdp_cid), '--pdp-seconds', str(args.pdp_seconds)]
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
                        '--confirm-private-nv-copy', '--runtime-helper', str(args.runtime_helper), '--seconds', '120'], check=True)
        print('Bounded RIL/RFS and cbd tests started; read private journal, not a success claim.')


if __name__ == '__main__':
    main()

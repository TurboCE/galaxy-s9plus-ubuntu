#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Start a bounded IPC/RFS test, then the own-vendor modem boot daemon.

Only for the manually reviewed G965N experimental driver. The owner CBD keeps
its original STATUS/conditional RESET startup flow; the parent does not force
a preliminary power transition. Never use during a live call.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import re
import importlib.util
import fcntl


def require_online_cp():
    fd = os.open('/dev/umts_ipc0', os.O_RDWR | os.O_NONBLOCK)
    try:
        if fcntl.ioctl(fd, 0x6f27, 0) != 4:  # IOCTL_MODEM_STATUS, STATE_ONLINE
            raise RuntimeError('Existing-online attachment requires STATE_ONLINE')
    finally:
        os.close(fd)


def load_runtime(helper):
    if helper.is_symlink() or not helper.is_file():
        raise RuntimeError('Missing reviewed vendor-runtime helper')
    spec = importlib.util.spec_from_file_location('g965n_runtime_preflight', helper)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime


def verify_private_runtime(helper, runtime=None):
    """Caller holds shared runtime lease; no unit/vendor launch before all checks pass."""
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
    parser.add_argument('--attach-online', action='store_true',
                        help='Attach to a status-verified online CP; never start CBD or reset it')
    parser.add_argument('--observe-only', action='store_true',
                        help='Online attachment with read-only SIM/AT status queries; no radio/PDP configuration')
    parser.add_argument('--diagnostic-status', action='store_true')
    parser.add_argument('--capture-private-rfs', action='store_true',
                        help='Capture bounded OPEN/CLOSE requests in the private lab, never NV payloads')
    parser.add_argument('--serve-private-rfs-diagnostics', action='store_true',
                        help='Opt in to two bounded new private diagnostic files; never original EFS')
    parser.add_argument('--scan-networks', action='store_true',
                        help='One bounded network scan; requires online observe-only mode and >=110seconds')
    parser.add_argument('--scan-networks-s9', action='store_true',
                        help='One stock-layout Samsung network scan; same observe-only guards')
    args = parser.parse_args()
    if getattr(args, 'scan_networks', False) and getattr(args, 'scan_networks_s9', False):
        parser.error('Choose one scan transport')
    if (getattr(args, 'scan_networks', False) or getattr(args, 'scan_networks_s9', False)) and (not getattr(args, 'observe_only', False) or
                                                 not getattr(args, 'attach_online', False) or
                                                 getattr(args, 'activate_pdp_s9', False) or args.seconds < 110):
        parser.error('Network scan requires online observe-only mode, no PDP activation and >=110seconds')
    if getattr(args, 'observe_only', False) and (not getattr(args, 'attach_online', False) or
                                                getattr(args, 'activate_pdp_s9', False)):
        parser.error('Observe-only requires online attachment and forbids PDP activation')
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
        if getattr(args, 'attach_online', False):
            require_online_cp()
        from gi.repository import Gio, GLib
        # Preserve owner CBD's own status-dependent reset/startup sequence.
        command = ['/usr/bin/python3', str((args.lab_directory / 'ril-lab.py').resolve()),
                   '--seconds', str(args.seconds), '--apn', args.apn,
                   '--runtime-helper', str(args.runtime_helper.resolve()),
                   '--expected-receipt-sha256', runtime.launch_receipt_digest()]
        if getattr(args, 'observe_only', False):
            command += ['--diagnostic-status']
        else:
            command += ['--configure-radio']
            if getattr(args, 'diagnostic_status', False):
                command += ['--diagnostic-status']
        if args.activate_pdp_s9:
            command += ['--activate-pdp-s9', '--confirm-reviewed-s9-pdp-layout',
                        '--pdp-cid', str(args.pdp_cid), '--pdp-seconds', str(args.pdp_seconds)]
        if getattr(args, 'attach_online', False):
            command += ['--attach-online']
        if getattr(args, 'scan_networks', False):
            command += ['--scan-networks']
        if getattr(args, 'scan_networks_s9', False):
            command += ['--scan-networks-s9']
        if getattr(args, 'capture_private_rfs', False):
            runtime.safe_components(args.lab_directory)
            command += ['--private-rfs-capture', str(args.lab_directory / 'rfs-open-requests.bin')]
        if getattr(args, 'serve_private_rfs_diagnostics', False):
            runtime.safe_components(args.lab_directory)
            command += ['--private-rfs-diagnostics', str(args.lab_directory / 'rfs-diagnostics')]
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
        if getattr(args, 'attach_online', False):
            print('Bounded RIL/RFS attached to verified online CP; no CBD start/reset requested.')
            return
        if subprocess.run(['systemctl', 'is-failed', '--quiet', 'g965n-cbd-test']).returncode == 0:
            subprocess.run(['systemctl', 'reset-failed', 'g965n-cbd-test'], check=True)
        subprocess.run([sys.executable, str(Path(__file__).with_name('run-cbd-test.py')),
                        '--confirm-private-nv-copy', '--runtime-helper', str(args.runtime_helper), '--seconds', '120'], check=True)
        print('Bounded RIL/RFS and cbd tests started; read private journal, not a success claim.')


if __name__ == '__main__':
    main()

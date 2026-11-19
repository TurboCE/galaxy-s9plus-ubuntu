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
import importlib.util
import sys
import tempfile

ROOT = Path('/run/g965n-vendor-runtime/root')
TRACE_DIR = Path('/var/lib/g965n-vendor-runtime')


def new_trace_path():
    info = TRACE_DIR.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise RuntimeError('Trace directory must be owned and private')
    fd, path = tempfile.mkstemp(prefix='cbd-', suffix='.strace', dir=TRACE_DIR)
    os.close(fd)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-private-nv-copy', action='store_true', required=True)
    parser.add_argument('--isolated-modem-runtime', action='store_true')
    parser.add_argument('--seconds', type=int, choices=(*range(10, 121), 315), default=60)
    parser.add_argument('--runtime-helper', type=Path, default=Path(__file__).with_name('vendor-runtime.py'))
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--expected-receipt-sha256', help=argparse.SUPPRESS)
    parser.add_argument('--trace', action='store_true', help='Private host strace around chroot/exec')
    args = parser.parse_args()
    if getattr(args, 'seconds', 60) == 315 and not args.isolated_modem_runtime:
        parser.error('Extended CBD lifetime requires the dedicated isolated modem view')
    if os.geteuid() != 0:
        raise SystemExit('Expected root and the prepared private vendor runtime')
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected star2lte')
    helper = args.runtime_helper
    if helper.is_symlink() or not helper.is_file():
        raise RuntimeError('Missing reviewed vendor-runtime helper')
    spec = importlib.util.spec_from_file_location('cbd_runtime_preflight', helper)
    runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
    if getattr(args, 'isolated_modem_runtime', False):
        runtime.select_modem_runtime()
    with runtime.shared_runtime_lock():
        if args.child:
            runtime.validate_launch_state(args.expected_receipt_sha256)
            command = vendor_command(args, runtime.ROOT)
            os.execv(command[0], command)
            raise RuntimeError('Vendor exec unexpectedly returned')
        runtime.assert_board()
        runtime.validate_modem_state(runtime.read_provenance())
        runtime.verify_private_bindings()
        launch(args, runtime)


def vendor_command(args, root=ROOT):
    command = ['/usr/sbin/chroot', str(root), '/vendor/bin/cbd', '-d',
               '-tss310', '-bm', '-mm', '-P',
               'platform/11120000.ufs/by-name/RADIO', '-n', '/mnt/vendor/efs']
    if args.trace:
        command = ['/usr/bin/strace', '-f', '-s', '100', '-o',
                   new_trace_path()] + command
    return command


def cbd_command(args, runtime):
    # A separate flock monitor retains the lease even if vendor code closes all
    # inherited descriptors. Child rechecks state after acquiring its own lease.
    command = ['/usr/bin/python3', str(Path(__file__).resolve()), '--child',
               '--confirm-private-nv-copy', '--runtime-helper', str(args.runtime_helper.resolve()),
               '--expected-receipt-sha256', runtime.launch_receipt_digest(),
               '--seconds', str(args.seconds)]
    isolated = getattr(args, 'isolated_modem_runtime', False)
    if isolated:
        command.append('--isolated-modem-runtime')
    if args.trace:
        command.append('--trace')
    paths = runtime.runtime_lock_paths() if isolated else (runtime.RUNTIME_LOCK,)
    for path in reversed(paths):
        command = ['/usr/bin/flock', '--shared', '--nonblock', str(path), *command]
    return command


def launch(args, runtime):
    from gi.repository import Gio, GLib
    allow = []
    for path in Path('/dev').glob('umts_*'):
        if not stat.S_ISCHR(path.stat().st_mode):
            raise SystemExit('Unexpected modem device type')
        allow.append((str(path), 'rw'))
    if not any(p.endswith('/umts_boot0') for p, _ in allow):
        raise SystemExit('Modem boot control node missing')
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
    command = cbd_command(args, runtime)
    executable = command[0]
    properties.append(('ExecStart', GLib.Variant('a(sasb)', [(executable, command, False)])))
    bus = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SYSTEM, 0, None,
        'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', None)
    bus.call_sync('StartTransientUnit', GLib.Variant('(ssa(sv)a(sa(sv)))', (
        'g965n-cbd-test.service', 'fail', properties, [])), 0, 5000, None)
    print('g965n-cbd-test.service started with closed device policy; inspect private logs.')


if __name__ == '__main__':
    main()

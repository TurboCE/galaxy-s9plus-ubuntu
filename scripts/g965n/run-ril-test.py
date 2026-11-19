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
import time


def wait_for_lab_ready(seconds=10):
    """A transient start job is not descriptor readiness. Require main notify."""
    if not 0 < seconds <= 10:
        raise ValueError('Bounded readiness wait required')
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        output = subprocess.check_output(['systemctl', 'show', 'g965n-ril-lab-test.service',
            '-p', 'Type', '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID', '-p', 'Result'],
            text=True, timeout=2)
        state = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
        if state.get('Type') != 'notify':
            raise RuntimeError('RIL readiness requires a notify service')
        active = state.get('ActiveState')
        if active == 'active':
            pid = state.get('MainPID', '')
            if (state.get('SubState') != 'running' or not pid.isdigit() or int(pid) <= 0
                    or state.get('Result') != 'success'):
                raise RuntimeError('RIL main process is not running after readiness')
            return
        if active != 'activating':
            raise RuntimeError('RIL failed before channel readiness')
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    raise TimeoutError('RIL channel readiness timed out; CBD not started')


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
    parser.add_argument('--isolated-modem-runtime', action='store_true')
    parser.add_argument('--seconds', type=int, choices=(*range(30, 121), 300), default=90)
    parser.add_argument('--activate-pdp-s9', action='store_true')
    parser.add_argument('--confirm-reviewed-s9-pdp-layout', action='store_true')
    parser.add_argument('--pdp-cid', type=int, choices=(1,), default=1)
    parser.add_argument('--pdp-seconds', type=int, choices=range(10,61), default=30)
    parser.add_argument('--hold-qualified-pdp', action='store_true')
    parser.add_argument('--export-ipv4-lease', action='store_true')
    parser.add_argument('--wwan-query-broker', action='store_true')
    parser.add_argument('--wwan-bearer-control', action='store_true')
    parser.add_argument('--cycle-qualified-pdp', action='store_true',
                        help='Allow a one-shot reconnect requested by a private lab marker')
    parser.add_argument('--attach-online', action='store_true',
                        help='Attach to a status-verified online CP; never start CBD or reset it')
    parser.add_argument('--observe-only', action='store_true',
                        help='Online attachment with read-only SIM/AT status queries; no radio/PDP configuration')
    parser.add_argument('--diagnostic-status', action='store_true')
    parser.add_argument('--capture-private-rfs', action='store_true',
                        help='Capture bounded OPEN/CLOSE requests in the private lab, never NV payloads')
    parser.add_argument('--serve-private-rfs-diagnostics', action='store_true',
                        help='Opt in to two bounded new private diagnostic files; never original EFS')
    parser.add_argument('--quiesce-radio-on-exit', action='store_true',
                        help='Cold test only: bounded RF low-power handshake/drain at exit, no physical reset')
    parser.add_argument('--scan-networks', action='store_true',
                        help='One bounded network scan; requires online observe-only mode and >=110seconds')
    parser.add_argument('--scan-networks-s9', action='store_true',
                        help='One stock-layout Samsung network scan; same observe-only guards')
    args = parser.parse_args()
    hold = getattr(args, 'hold_qualified_pdp', False)
    export_lease = getattr(args, 'export_ipv4_lease', False)
    wwan_broker = getattr(args, 'wwan_query_broker', False)
    if wwan_broker and (not hold or not args.isolated_modem_runtime):
        parser.error('WWAN queries require an isolated held PDP trial')
    soak = getattr(args, 'seconds', 90) == 300
    if soak and (not export_lease or not hold or not args.isolated_modem_runtime
                 or args.attach_online or not args.quiesce_radio_on_exit):
        parser.error('300-second soak requires isolated held IPv4 with cold shutdown cleanup')
    if export_lease and (not hold or not args.isolated_modem_runtime):
        parser.error('IPv4 lease requires an isolated held PDP trial')
    cycle = getattr(args, 'cycle_qualified_pdp', False)
    wwan_control = getattr(args, 'wwan_bearer_control', False)
    if wwan_control and (not wwan_broker or not export_lease or cycle):
        parser.error('WWAN bearer control requires the WWAN broker and IPv4 lease without the cycle marker')
    if cycle and (not hold or not args.isolated_modem_runtime):
        parser.error('PDP cycle requires a held cold trial in an isolated modem runtime')
    if hold and (not args.activate_pdp_s9 or args.attach_online or not args.quiesce_radio_on_exit):
        parser.error('Held PDP requires a bounded cold PDP trial with radio cleanup')
    if getattr(args, 'quiesce_radio_on_exit', False) and (
            getattr(args, 'attach_online', False) or getattr(args, 'observe_only', False)):
        parser.error('Radio quiesce is cold-test only, never existing-online observation')
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
    isolated = getattr(args, 'isolated_modem_runtime', False)
    if isolated:
        runtime.select_modem_runtime()
    with runtime.shared_runtime_lock():
        verify_private_runtime(args.runtime_helper, runtime)
        if getattr(args, 'attach_online', False):
            require_online_cp()
        from gi.repository import Gio, GLib
        # Preserve owner CBD's own status-dependent reset/startup sequence.
        command = ['/usr/bin/python3', str((args.lab_directory / 'ril-lab.py').resolve()),
                   '--seconds', str(args.seconds), '--apn', args.apn,
                   '--runtime-helper', str(args.runtime_helper.resolve()),
                   '--expected-receipt-sha256', runtime.launch_receipt_digest(), '--notify-ready']
        if isolated:
            command += ['--isolated-modem-runtime']
        if getattr(args, 'observe_only', False):
            command += ['--diagnostic-status']
        else:
            command += ['--configure-radio']
            if getattr(args, 'diagnostic_status', False):
                command += ['--diagnostic-status']
        if args.activate_pdp_s9:
            command += ['--activate-pdp-s9', '--confirm-reviewed-s9-pdp-layout',
                        '--pdp-cid', str(args.pdp_cid), '--pdp-seconds', str(args.pdp_seconds)]
            if hold:
                command.append('--hold-qualified-pdp')
            if export_lease:
                command.append('--export-ipv4-lease')
            if wwan_broker:
                command.append('--wwan-query-broker')
            if wwan_control:
                command.append('--wwan-bearer-control')
            if cycle:
                command += ['--pdp-cycle-request', str(args.lab_directory.resolve() / 'cycle-requested')]
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
        if getattr(args, 'quiesce_radio_on_exit', False):
            command += ['--quiesce-radio-on-exit']
        properties = [
            ('Description', GLib.Variant('s', 'Bounded G965N private-copy IPC/RFS lab')),
            ('Type', GLib.Variant('s', 'notify')),
            ('NotifyAccess', GLib.Variant('s', 'main')),
            ('TimeoutStartUSec', GLib.Variant('t', 10 * 1000000)),
            ('DevicePolicy', GLib.Variant('s', 'closed')),
            ('DeviceAllow', GLib.Variant('a(ss)', [('/dev/' + p, 'rw') for p in ('umts_ipc0', 'umts_rfs0', 'umts_router')])),
            ('UMask', GLib.Variant('u', 0o077)),
            ('NoNewPrivileges', GLib.Variant('b', True)),
            ('RuntimeMaxUSec', GLib.Variant('t', (args.seconds + (
                15 if getattr(args, 'quiesce_radio_on_exit', False) else 5)) * 1000000)),
            ('Restart', GLib.Variant('s', 'no')),
            ('ExecStart', GLib.Variant('a(sasb)', [(command[0], command, False)])),
        ]
        bus = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SYSTEM, 0, None,
            'org.freedesktop.systemd1', '/org/freedesktop/systemd1', 'org.freedesktop.systemd1.Manager', None)
        bus.call_sync('StartTransientUnit', GLib.Variant('(ssa(sv)a(sa(sv)))', (
            'g965n-ril-lab-test.service', 'fail', properties, [])), 0, 5000, None)
        try:
            wait_for_lab_ready()
        except BaseException:
            subprocess.run(['systemctl', 'stop', 'g965n-ril-lab-test.service'], timeout=15)
            raise
        print('RIL main process confirmed IPC/RFS ready before CBD launch.', flush=True)
        if getattr(args, 'attach_online', False):
            print('Bounded RIL/RFS attached to verified online CP; no CBD start/reset requested.')
            return
        if subprocess.run(['systemctl', 'is-failed', '--quiet', 'g965n-cbd-test']).returncode == 0:
            subprocess.run(['systemctl', 'reset-failed', 'g965n-cbd-test'], check=True)
        cbd = [sys.executable, str(Path(__file__).with_name('run-cbd-test.py')),
               '--confirm-private-nv-copy', '--runtime-helper', str(args.runtime_helper),
               '--seconds', '315' if soak else '120']
        if isolated:
            cbd.append('--isolated-modem-runtime')
        subprocess.run(cbd, check=True)
        print('Bounded RIL/RFS and cbd tests started; read private journal, not a success claim.')


if __name__ == '__main__':
    main()

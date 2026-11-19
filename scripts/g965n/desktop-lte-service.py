#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run the opt-in SM-G965N desktop LTE service for one systemd lifetime."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import uuid
import subprocess
import sys
import time

WORK = Path('/run/g965n-desktop-lte')
ATTEMPT = Path('/run/g965n-desktop-lte-attempted')
DROPIN = Path('/run/systemd/system/ModemManager.service.d/90-g965n-desktop-lte.conf')
MM = '/usr/sbin/ModemManager'
DEVICE = Path('/sys/devices/platform/10000.mif_pdata/net/rmnet0')
PROFILE = 'G965N mobile data'
PROGRAMS = {
    'run-ril-test.py', 'run-cbd-test.py', 'ril-lab.py', 'rfs-copy.py',
    'vendor-runtime.py', 'desktop-lte-service.py', 'lte-boot-session.py',
    'modem/g965n-modem.ko', 'mm/ModemManager', 'mm/lib/libmm-glib.so.0',
    'mm/plugins/libmm-plugin-generic.so', 'mm/plugins/libmm-plugin-samsung-sipc.so',
}


def call(*args, check=True, timeout=20):
    return subprocess.run(args, check=check, capture_output=True, text=True, timeout=timeout)


def value(*args):
    return call(*args).stdout.strip()


def active_state(unit):
    return value('systemctl', 'show', unit, '-p', 'ActiveState', '--value')


def launch_argv(root, profile):
    return [sys.executable, str(root / 'run-ril-test.py'),
            '--lab-directory', str(root), '--runtime-helper', str(root / 'vendor-runtime.py'),
            '--confirm-private-nv-copy', '--isolated-modem-runtime', '--service-lifetime',
            '--apn', profile['apn'], '--quiesce-radio-on-exit',
            '--activate-pdp-s9', '--confirm-reviewed-s9-pdp-layout', '--pdp-seconds', '20',
            '--hold-qualified-pdp', '--export-ipv4-lease',
            '--wwan-query-broker', '--wwan-bearer-control']


def original_manager():
    pid = int(value('systemctl', 'show', 'ModemManager', '-p', 'MainPID', '--value'))
    return pid > 0 and Path('/proc', str(pid), 'exe').resolve() == Path(MM)


def checked_children(boot):
    for unit in (boot.RIL, boot.CBD):
        if active_state(unit) != 'active':
            raise RuntimeError('Desktop modem child exited: ' + unit)


def restore_desktop():
    if not WORK.is_dir():
        return
    profile_path = WORK / 'profile-uuid'
    override_path = WORK / 'override'
    try:
        if profile_path.is_file():
            identifier = profile_path.read_text().strip()
            if re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', identifier):
                name = call('nmcli', '-g', 'connection.id', 'connection', 'show', identifier,
                            check=False).stdout.strip()
                if name == PROFILE:
                    call('nmcli', '--wait', '10', 'connection', 'delete', 'uuid', identifier)
                elif name:
                    raise RuntimeError('Temporary LTE profile ownership changed')
            profile_path.unlink()
    finally:
        restore_manager(override_path)


def restore_manager(override_path):
    if override_path.is_file() and DROPIN.is_file():
        if DROPIN.read_bytes() != override_path.read_bytes():
            raise RuntimeError('ModemManager override differs from the owned file')
        DROPIN.unlink()
        call('systemctl', 'daemon-reload')
        call('systemctl', 'restart', 'ModemManager', timeout=35)
    if override_path.is_file():
        if not original_manager():
            call('systemctl', 'daemon-reload')
            call('systemctl', 'restart', 'ModemManager', timeout=35)
        if not original_manager():
            raise RuntimeError('Could not restore original ModemManager')
        override_path.unlink()


def start_desktop(root, profile):
    data = WORK / 'udev-data'
    data.mkdir(mode=0o700)
    index = int((DEVICE / 'ifindex').read_text())
    (data / f'n{index}').write_text('I:1\nE:ID_MM_CANDIDATE=1\nE:ID_MM_G965N_SIPC=1\n')
    override = (f'[Service]\nExecStart=\nExecStart={root}/mm/ModemManager '
                f'--test-plugin-dir={root}/mm/plugins\nEnvironment=LD_LIBRARY_PATH={root}/mm/lib\n'
                f'BindReadOnlyPaths={data}:/run/udev/data\n')
    DROPIN.parent.mkdir(parents=True, exist_ok=True)
    with (WORK / 'override').open('x') as marker:
        marker.write(override)
    with DROPIN.open('x') as output:
        output.write(override)
    call('systemctl', 'daemon-reload')
    call('systemctl', 'restart', 'ModemManager', timeout=35)
    if profile['auto_profile']:
        identifier = str(uuid.uuid4())
        (WORK / 'profile-uuid').write_text(identifier)
        call('nmcli', '--wait', '10', 'connection', 'add', 'save', 'no', 'type', 'gsm',
             'ifname', 'rmnet0', 'con-name', PROFILE, 'connection.uuid', identifier,
             'gsm.apn', profile['apn'], 'connection.autoconnect', 'yes',
             'ipv4.method', 'auto', 'ipv4.route-metric', '20000', 'ipv6.method', 'disabled')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--config-sha256')
    parser.add_argument('--confirm-desktop-lte', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Desktop LTE service requires root')
    os.umask(0o077)
    if args.cleanup:
        restore_desktop()
        return
    if not (args.confirm_desktop_lte and args.config and args.config_sha256):
        parser.error('An explicitly approved desktop LTE profile and its digest are required')
    root = args.config.parent
    if not re.fullmatch(r'/var/lib/g965n-lte/[A-Za-z0-9_-]+', str(root)):
        raise ValueError('Expected dedicated private desktop LTE directory')
    if root.resolve(strict=True) != root:
        raise ValueError('Service directory must have a canonical path')
    for directory in (root, *root.parents):
        st = directory.stat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & (0o077 if directory == root else 0o022):
            raise ValueError('Expected a root-private service directory and protected parents')

    from importlib.util import module_from_spec, spec_from_file_location

    helper_path = root / 'lte-boot-session.py'
    info = helper_path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o022:
        raise ValueError('Expected a protected desktop LTE boot helper')
    helper = spec_from_file_location('g965n_lte_boot', helper_path)
    boot = module_from_spec(helper)
    helper.loader.exec_module(boot)
    cfg = json.loads(boot.trusted(args.config, args.config_sha256, 65536))
    if (cfg['model'] != 'SM-G965N' or set(cfg['files']) != PROGRAMS
            or type(cfg['auto_profile']) is not bool or not re.fullmatch(r'[A-Za-z0-9.-]{1,100}', cfg['apn'])):
        raise ValueError('Unexpected desktop LTE configuration')
    for name, digest in cfg['files'].items():
        boot.trusted(root / name, digest, 32 * 1024 * 1024)
    profile = Path(cfg['kernel_profile'])
    guard = profile / 'package/p2p-control-trial.py'
    boot.trusted(guard, cfg['guard_sha256'], 512 * 1024)
    check = boot.load(guard)
    bundle = check.trusted_json(profile / 'startup.json', cfg['receipt_sha256'])
    backup = check.trusted_json(profile / 'backup.json', cfg['backup_sha256'])
    check.validate(bundle, backup, require_off=False)
    modem_module = root / 'modem/g965n-modem.ko'
    stock_module = profile / 'package' / bundle['modules']['modem']['path']
    boot.trusted(stock_module, bundle['modules']['modem']['sha256'], 32 * 1024 * 1024)
    if value('modinfo', '-F', 'vermagic', str(modem_module)) != value(
            'modinfo', '-F', 'vermagic', str(stock_module)):
        raise RuntimeError('Desktop modem module vermagic mismatch')
    overlay = bundle['artifacts']['modem_overlay']
    if overlay['stock_verification']['status'] != 'passed' or overlay['stock_verification']['revision'] != 26:
        raise RuntimeError('Expected revision-qualified modem overlay')
    relative_fw = Path(overlay['firmware_request'])
    if relative_fw.is_absolute() or '..' in relative_fw.parts:
        raise ValueError('Unexpected modem firmware path')
    boot.trusted(Path('/usr/lib/firmware') / relative_fw, overlay['sha256'], 512 * 1024)
    deadline = time.monotonic() + 25
    while active_state('ModemManager') in ('inactive', 'activating') and time.monotonic() < deadline:
        time.sleep(.5)
    if (Path('/sys/module/g965n_modem').exists() or DROPIN.exists() or DROPIN.is_symlink()
            or not original_manager() or 'No modems were found' not in value('mmcli', '-L')):
        raise RuntimeError('Desktop LTE requires a clean modem stack and idle stock manager')
    if cfg['auto_profile'] and call('nmcli', '-g', 'connection.id', 'connection', 'show', PROFILE,
                                    check=False).returncode == 0:
        raise RuntimeError('Desktop LTE profile already exists')
    vr = boot.load(root / 'vendor-runtime.py')
    vr.assert_board()
    vr.select_modem_runtime()
    stop = False

    def requested_stop(_signal, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, requested_stop)
    signal.signal(signal.SIGINT, requested_stop)
    ATTEMPT.touch(mode=0o600, exist_ok=False)
    WORK.mkdir(mode=0o700)
    prepared = False
    try:
        with vr.checked_lock(vr.STATE_LOCK, vr.fcntl.LOCK_EX), vr.checked_lock(vr.RUNTIME_LOCK, vr.fcntl.LOCK_EX):
            vr.assert_modem_stopped()
            if vr.ROOT.is_mount():
                raise RuntimeError('Modem runtime is already mounted')
            vr.validate_modem_state(vr.read_provenance())
            vr.prepare()
            prepared = True
            vr.modem_bindings_absent()
            call('/usr/sbin/insmod', str(modem_module), 'enable_g965n=1', 'link_wwan_parent=1', timeout=30)
            if Path('/sys/class/net/rmnet0').resolve(strict=True) != DEVICE:
                raise RuntimeError('Unexpected modem data port')
            vr.resume_modem()
            vr.device_nodes()
            vr.cbd_permissions()
            vr.verify_private_bindings()
        if stop:
            return
        call(*launch_argv(root, cfg), timeout=30)
        deadline = time.monotonic() + 5
        while not stop and active_state(boot.CBD) == 'activating' and time.monotonic() < deadline:
            time.sleep(.25)
        if stop:
            return
        checked_children(boot)
        started = time.monotonic()
        invocation = value('systemctl', 'show', boot.RIL, '-p', 'InvocationID', '--value')
        if not re.fullmatch(r'[a-f0-9]{32}', invocation):
            raise RuntimeError('Unexpected RIL invocation')
        while not stop and time.monotonic() - started < 40:
            checked_children(boot)
            endpoint = Path('/run') / f'g965n-wwan-{invocation}.sock'
            if endpoint.is_socket():
                with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as sock:
                    sock.settimeout(4)
                    sock.connect(str(endpoint))
                    sock.sendall(b'sim-readiness')
                    if json.loads(sock.recv(1024)) == {'sim_ready': True}:
                        break
            time.sleep(.5)
        else:
            if stop:
                return
            raise RuntimeError('Modem did not report a ready SIM')
        start_desktop(root, cfg)
        while not stop:
            checked_children(boot)
            time.sleep(2)
    finally:
        try:
            restore_desktop()
        finally:
            for unit in (boot.RIL, boot.CBD):
                if active_state(unit) not in ('inactive', 'failed'):
                    call('systemctl', 'stop', unit, timeout=35)
            if prepared:
                with vr.modem_runtime_setup_lock():
                    vr.assert_modem_stopped()
                    if vr.ROOT.is_mount():
                        vr.teardown()


if __name__ == '__main__':
    main()

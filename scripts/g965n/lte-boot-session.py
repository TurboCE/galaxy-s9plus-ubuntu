#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run one explicitly armed G965N IPv4 boot validation session."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

RIL = 'g965n-ril-lab-test.service'
CBD = 'g965n-cbd-test.service'
ROUTE = 'g965n-lte-route-boot.service'
FILES = {'run-ril-test.py', 'ril-lab.py', 'run-cbd-test.py', 'rfs-copy.py',
         'vendor-runtime.py', 'lte-route-owner.py', 'lte-boot-session.py'}
ATTEMPT = Path('/run/g965n-lte-boot-attempted')
WORK = Path('/run/g965n-lte-boot.d')


def run(*argv, timeout=10, check=True):
    return subprocess.run(argv, check=check, capture_output=True, text=True, timeout=timeout)


def unit_state(unit):
    return dict(line.split('=', 1) for line in run(
        'systemctl', 'show', unit, '-p', 'ActiveState', '-p', 'InvocationID',
        '-p', 'LoadState', '-p', 'Result').stdout.splitlines())


def trusted(path, fingerprint, limit):
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected a protected absolute path')
    for parent in path.parents:
        st = parent.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise ValueError('Unprotected input parent')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        st = os.fstat(stream.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1
                or st.st_mode & 0o022 or st.st_size > limit):
            raise ValueError('Unsafe or oversized input')
        data = stream.read(limit + 1)
    if len(data) > limit or hashlib.sha256(data).hexdigest() != fingerprint:
        raise ValueError('Input checksum mismatch')
    return data


def load(path):
    spec = importlib.util.spec_from_file_location('g965n_boot_' + path.stem, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--confirm-bounded-boot-trial', action='store_true', required=True)
    parser.add_argument('--soak', action='store_true', help='Run the explicit 300-second qualification')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Expected root on SM-G965N')
    os.umask(0o077)
    root = args.config.parent
    if not re.fullmatch(r'/var/lib/g965n-lte/[A-Za-z0-9_-]+', str(root)):
        raise ValueError('Expected dedicated private LTE program directory')
    if root.stat().st_mode & 0o077:
        raise ValueError('LTE program directory must be private')
    cfg = json.loads(trusted(args.config, args.config_sha256, 65536))
    if (cfg['model'] != 'SM-G965N' or set(cfg['files']) != FILES
            or not re.fullmatch(r'[A-Za-z0-9.-]{1,100}', cfg['apn'])):
        raise ValueError('Unexpected LTE profile')
    sources = {name: trusted(root / name, digest, 512 * 1024)
               for name, digest in cfg['files'].items()}
    arm = root / 'armed'
    trusted(arm, hashlib.sha256(b'armed\n').hexdigest(), 16)
    profile = Path(cfg['kernel_profile'])
    guard = profile / 'package/p2p-control-trial.py'
    trusted(guard, cfg['guard_sha256'], 512 * 1024)
    g = load(guard)
    receipt = g.trusted_json(profile / 'startup.json', cfg['receipt_sha256'])
    backup = g.trusted_json(profile / 'backup.json', cfg['backup_sha256'])
    g.validate(receipt, backup, require_off=False)
    if Path('/sys/module/g965n_modem').exists():
        raise RuntimeError('A modem module is already loaded; no cold restart')
    for unit in (RIL, CBD, ROUTE):
        state = unit_state(unit)
        if state.get('LoadState') != 'not-found' or state.get('ActiveState') != 'inactive':
            raise RuntimeError('Prior LTE unit already exists')
    mod = receipt['modules']['modem']
    overlay = receipt['artifacts']['modem_overlay']
    if (mod['path'] != 'modem/g965n-modem.ko' or
            overlay['stock_verification']['status'] != 'passed' or
            overlay['stock_verification']['revision'] != 26):
        raise ValueError('Unexpected modem module or stock overlay qualification')
    relative_fw = Path(overlay['firmware_request'])
    if relative_fw.is_absolute() or '..' in relative_fw.parts:
        raise ValueError('Unexpected modem firmware path')
    module = profile / 'package' / mod['path']
    trusted(module, mod['sha256'], 32 * 1024 * 1024)
    trusted(Path('/usr/lib/firmware') / relative_fw, overlay['sha256'], 512 * 1024)
    vr = load(root / 'vendor-runtime.py')
    vr.assert_board()
    vr.select_modem_runtime()
    stop = False

    def request_stop(_signal, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    prepared = children = False
    try:
        with vr.checked_lock(vr.STATE_LOCK, vr.fcntl.LOCK_EX), vr.checked_lock(vr.RUNTIME_LOCK, vr.fcntl.LOCK_EX):
            vr.assert_modem_stopped()
            if vr.ROOT.is_mount() or Path('/sys/module/g965n_modem').exists():
                raise RuntimeError('Modem runtime already exists')
            vr.validate_modem_state(vr.read_provenance())
            ATTEMPT.touch(mode=0o600, exist_ok=False)
            if stop:
                return
            arm.unlink()
            WORK.mkdir(mode=0o700)
            for name, data in sources.items():
                with (WORK / name).open('xb') as stream:
                    stream.write(data)
            prepared = True
            vr.prepare()
            vr.modem_bindings_absent()
            run('/usr/sbin/insmod', str(module), 'enable_g965n=1', timeout=30)
            vr.resume_modem()
            vr.verify_private_bindings()
        if stop:
            return
        children = True
        seconds = 300 if args.soak else 120
        launch = run(sys.executable, str(WORK / 'run-ril-test.py'),
                     '--lab-directory', str(WORK), '--runtime-helper', str(WORK / 'vendor-runtime.py'),
                     '--confirm-private-nv-copy', '--isolated-modem-runtime',
                     '--apn', cfg['apn'], '--seconds', str(seconds), '--serve-private-rfs-diagnostics',
                     '--quiesce-radio-on-exit', '--activate-pdp-s9',
                     '--confirm-reviewed-s9-pdp-layout', '--pdp-seconds', '20',
                     '--hold-qualified-pdp', '--export-ipv4-lease', timeout=28, check=False)
        if launch.returncode:
            print(launch.stdout, file=sys.stderr)
            print(launch.stderr, file=sys.stderr)
            raise RuntimeError('LTE child launch failed')
        state = unit_state(RIL)
        invocation = state.get('InvocationID', '')
        if state.get('ActiveState') != 'active' or not re.fullmatch(r'[a-f0-9]{32}', invocation):
            raise RuntimeError('RIL readiness or invocation missing')
        owner = [sys.executable, str(WORK / 'lte-route-owner.py'),
                 '--invocation', invocation, '--confirm-guarded-g965n-route']
        run('systemd-run', '--unit=' + ROUTE, '--property=BindsTo=' + RIL,
            '--property=After=' + RIL, '--property=RuntimeMaxSec=' + str(seconds + 15),
            '--property=TimeoutStopSec=20', '--property=NoNewPrivileges=yes',
            '--property=ExecStopPost=' + ' '.join([*owner, '--cleanup']), *owner)
        print('Bounded boot LTE controller started its qualified RIL and route owner.', flush=True)
        while not stop:
            state = unit_state(RIL)
            if state.get('ActiveState') != 'active' or state.get('InvocationID') != invocation:
                if state.get('Result') != 'success':
                    raise RuntimeError('RIL stopped with failure')
                break
            if unit_state(ROUTE).get('ActiveState') == 'failed':
                raise RuntimeError('LTE route owner failed')
            time.sleep(.5)
    finally:
        if children:
            for unit in (ROUTE, RIL, CBD):
                if unit_state(unit).get('ActiveState') not in ('inactive', 'failed'):
                    run('systemctl', 'stop', unit, timeout=25)
        if prepared:
            with vr.modem_runtime_setup_lock():
                vr.assert_modem_stopped()
                if vr.ROOT.is_mount():
                    vr.teardown()
                vr.validate_modem_state(vr.read_provenance())
            print('Boot LTE controller cleaned its runtime; modem module remains until reboot.', flush=True)


if __name__ == '__main__':
    main()

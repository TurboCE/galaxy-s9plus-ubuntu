#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded SM-G965N rumble start/stop/test, with an independent rail-off fallback."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess

ROOT = Path('/usr/local/lib/g965n-haptic-trial')
BOARD = Path('/sys/bus/platform/devices/g965n-haptic-board')
CHILD = Path('/sys/bus/platform/devices/max77705-haptic')
DRIVER = 'g965n-max77705-haptic'
MODULES = ('g965n-pwm-board.ko', 'g965n-haptic-board.ko', 'ff-memless.ko', 'g965n-haptic-trial.ko')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def check_private(path):
    for p in (path, *path.parents):
        info = p.lstat()
        require(not p.is_symlink() and info.st_uid == 0 and not info.st_mode & 0o022,
                'Unprotected runtime path')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not info.st_mode & 0o077,
            'Expected root-private regular input')


def preflight():
    require(os.geteuid() == 0, 'Root required')
    state = Path('/var/lib/g965n-sensors')
    raw = (state / 'profile.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == (state / 'profile.sha256').read_text().split()[0],
            'Profile pin mismatch')
    p = json.loads(raw)
    package = Path(p['kernel_receipt']['path']).parent / 'package'
    guard = load(package / 'p2p-control-trial.py', 'haptic_guard')
    receipt = guard.trusted_json(Path(p['kernel_receipt']['path']), p['kernel_receipt']['sha256'])
    backup = guard.trusted_json(Path(p['backup_manifest']['path']), p['backup_manifest']['sha256'])
    guard.validate(receipt, backup, require_off=False)
    require(receipt['kernel_version'].startswith('#48 '), 'Unqualified running kernel')
    entries = {e['name']: e for e in backup['partitions']}
    for name, node in {'RECOVERY':'sda11', 'EFS':'sda3', 'CPEFS':'sdd1', 'RADIO':'sda12'}.items():
        value = subprocess.check_output(['sha256sum', '/dev/' + node], text=True).split()[0]
        require(value == entries[name]['sha256'], 'Protected partition backup mismatch: ' + name)
    check_private(ROOT / 'pins.json')
    pins = json.loads((ROOT / 'pins.json').read_text())
    require(set(pins) == set(MODULES), 'Unexpected module set')
    for name, expected in pins.items():
        path = ROOT / name
        check_private(path)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Module pin mismatch')
        magic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(path)], text=True).strip()
        require(magic == os.uname().release + ' SMP preempt mod_unload aarch64', 'Module ABI mismatch')


def module_name(filename):
    return filename.removesuffix('.ko').replace('-', '_')


def cut_power():
    path = BOARD / 'emergency_off'
    if path.exists():
        path.write_text('1\n')


def start():
    if (CHILD / 'driver').exists():
        require((CHILD / 'driver').resolve().name == DRIVER, 'Existing haptic driver preserved')
        return
    loaded = []
    try:
        for filename in MODULES:
            if Path('/sys/module', module_name(filename)).exists():
                continue
            command = ['insmod', str(ROOT / filename)]
            if filename.endswith('-board.ko'):
                command.append('enable_g965n=1')
            subprocess.run(command, check=True, timeout=15)
            loaded.append(filename)
        require((CHILD / 'driver').exists() and (CHILD / 'driver').resolve().name == DRIVER,
                'Rumble driver did not bind')
    except Exception:
        cut_power()
        for filename in reversed(loaded):
            subprocess.run(['rmmod', module_name(filename)], check=False, timeout=15)
        raise


def stop():
    cut_power()
    if (CHILD / 'driver').exists():
        require((CHILD / 'driver').resolve().name == DRIVER, 'Existing haptic driver preserved')
    for filename in ('g965n-haptic-trial.ko', 'g965n-haptic-board.ko', 'g965n-pwm-board.ko'):
        if Path('/sys/module', module_name(filename)).exists():
            subprocess.run(['rmmod', module_name(filename)], check=True, timeout=15)


def test(duration, magnitude):
    require((CHILD / 'driver').exists() and (CHILD / 'driver').resolve().name == DRIVER,
            'Trial driver not started')
    manifest = ROOT / 'program-pins.json'
    check_private(manifest)
    pins = json.loads(manifest.read_text())
    path = ROOT / 'haptic-test'
    check_private(path)
    require(hashlib.sha256(path.read_bytes()).hexdigest() == pins['haptic-test'], 'Test program pin mismatch')
    events = [p for p in Path('/sys/class/input').glob('event*/device/name')
              if p.read_text().strip() == DRIVER]
    require(len(events) == 1, 'Ambiguous motor input')
    unit = 'g965n-haptic-rail-off-' + str(os.getpid())
    subprocess.run(['systemd-run', '--quiet', '--unit=' + unit, '--on-active=3s',
                    '--timer-property=AccuracySec=100ms', '/bin/sh', '-c',
                    'echo 1 > /sys/bus/platform/devices/g965n-haptic-board/emergency_off'], check=True)
    passed = False
    try:
        subprocess.run([str(path), '/dev/input/' + events[0].parents[1].name,
                        str(duration), str(magnitude)], check=True, timeout=2.5)
        passed = True
    finally:
        cut_power()
        if passed:
            subprocess.run(['systemctl', 'stop', unit + '.timer'], check=True)
    print('Bounded rumble and stop passed; motor rail off')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('start', 'stop', 'test'))
    p.add_argument('--confirm-sm-g965n-backed-up-haptic-trial', action='store_true', required=True)
    p.add_argument('--duration-ms', type=int, default=100)
    p.add_argument('--magnitude', type=int, default=8192)
    args = p.parse_args()
    if not 50 <= args.duration_ms <= 300 or not 4096 <= args.magnitude <= 16384:
        p.error('Trial bounds: duration50..300ms, magnitude4096..16384')
    os.umask(0o077)
    preflight()
    fd = os.open('/run/g965n-haptic-trial.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and not info.st_mode & 0o077, 'Invalid trial lock')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'test':
            test(args.duration_ms, args.magnitude)
        else:
            {'start': start, 'stop': stop}[args.action]()
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()

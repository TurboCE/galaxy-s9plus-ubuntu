#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit guarded lifecycle for the optional native48 input-QoS module."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/usr/local/lib/g965n-interactive-boost')
NAME = 'g965n_interactive_boost'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['start', 'stop'])
    p.add_argument('--confirm-sm-g965n-backed-up-interactive-trial', action='store_true', required=True)
    a = p.parse_args()
    if os.geteuid() != 0:
        p.error('Root is required for explicit device changes')
    os.umask(0o077)
    guard_path = Path('/usr/local/lib/g965n-haptic-trial/haptic-control.py')
    info = guard_path.lstat()
    if guard_path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077:
        p.error('Expected existing root-private native48 guard')
    spec = importlib.util.spec_from_file_location('native48_guard', guard_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.preflight()  # Actual SM-G965N, BOOT, qualified ABI and protected backups.
    pin = ROOT / 'pins.json'
    module = ROOT / 'g965n-interactive-boost.ko'
    for f in [pin, module, Path(__file__)]:
        guard.check_private(f)
    pins = json.loads(pin.read_text())
    module_sha = hashlib.sha256(module.read_bytes()).hexdigest()
    guard.require(pins == {module.name: module_sha}, 'Module pin drifted')
    magic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(module)], text=True).strip()
    guard.require(magic == os.uname().release + ' SMP preempt mod_unload aarch64', 'Kernel ABI mismatch')
    with (ROOT / 'lifecycle.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        statefile = ROOT / 'loaded.private.json'
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        loaded = Path('/sys/module', NAME).exists()
        if loaded:
            guard.check_private(statefile)
            state = json.loads(statefile.read_text())
            guard.require(state.get('boot') == boot and state.get('module_sha256') == module_sha,
                          'Unowned loaded module preserved')
        if a.action == 'start':
            if not loaded:
                original = {policy.name: int((policy / 'scaling_min_freq').read_text())
                            for policy in Path('/sys/devices/system/cpu/cpufreq').glob('policy*')}
                subprocess.run(['insmod', str(module), 'enable_g965n=1', 'hold_ms=500'], check=True)
                try:
                    statefile.write_text(json.dumps({'boot': boot, 'module_sha256': module_sha,
                                                     'original_minima': original}, indent=2)+'\n')
                    statefile.chmod(0o600)
                except BaseException:
                    subprocess.run(['rmmod', NAME], check=True)
                    raise
            guard.require(Path('/sys/module', NAME, 'parameters/hold_ms').read_text().strip() == '500',
                          'Unexpected active input-boost interval')
            print('Guarded input-QoS module started; no permanent frequency floor')
        elif loaded:
            subprocess.run(['rmmod', NAME], check=True)
            print('Input-QoS requests removed; other policy constraints preserved')


if __name__ == '__main__':
    main()

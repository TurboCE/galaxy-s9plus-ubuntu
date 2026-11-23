#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Model/BOOT/backup guarded low-current LED start, test and stop. Never flashes."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

ROOT = Path('/usr/local/lib/g965n-led-trial')
DEVICE = Path('/sys/bus/platform/devices/max77705-rgb')
DRIVER = 'g965n-max77705-led'
COLORS = ('red', 'green', 'blue')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def preflight():
    require(os.geteuid() == 0, 'Root required')
    state = Path('/var/lib/g965n-sensors')
    raw = (state / 'profile.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == (state / 'profile.sha256').read_text().split()[0], 'Profile pin mismatch')
    profile = json.loads(raw)
    package = Path(profile['kernel_receipt']['path']).parent / 'package'
    guard = load(package / 'p2p-control-trial.py', 'led_guard')
    receipt = guard.trusted_json(Path(profile['kernel_receipt']['path']), profile['kernel_receipt']['sha256'])
    backup = guard.trusted_json(Path(profile['backup_manifest']['path']), profile['backup_manifest']['sha256'])
    guard.validate(receipt, backup, require_off=False)
    require(receipt['kernel_version'].startswith(('#48 ', '#49 ', '#50 ')), 'Unqualified kernel trial')
    entries = {e['name']: e for e in backup['partitions']}
    for name, node in {'RECOVERY':'sda11', 'EFS':'sda3', 'CPEFS':'sdd1', 'RADIO':'sda12'}.items():
        actual = subprocess.check_output(['sha256sum', '/dev/' + node], text=True).split()[0]
        require(actual == entries[name]['sha256'], 'Protected backup mismatch: ' + name)
    pins = json.loads((ROOT / 'pins.json').read_text())
    require(set(pins) == {'leds-g965n-trial.ko', 'led-class-multicolor.ko'}, 'Unexpected module set')
    for name, expected in pins.items():
        module = ROOT / name
        info = module.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o077,
                'Unprotected module')
        require(hashlib.sha256(module.read_bytes()).hexdigest() == expected, 'Module pin mismatch')
        magic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(module)], text=True).strip()
        require(magic == os.uname().release + ' SMP preempt mod_unload aarch64', 'Module ABI mismatch')


def bound():
    return (DEVICE / 'driver').exists() and (DEVICE / 'driver').resolve().name == DRIVER


def start():
    if bound():
        return
    require(not (DEVICE / 'driver').exists(), 'Existing driver preserved')
    require((DEVICE / 'driver_override').read_text().strip() in ('', '(null)'), 'Existing override preserved')
    if not Path('/sys/module/led_class_multicolor').exists():
        subprocess.run(['insmod', str(ROOT / 'led-class-multicolor.ko')], check=True)
    require(not Path('/sys/module/leds_g965n_trial').exists(), 'Unowned preloaded trial module')
    subprocess.run(['insmod', str(ROOT / 'leds-g965n-trial.ko')], check=True)
    try:
        (DEVICE / 'driver_override').write_text(DRIVER + '\n')
        (Path('/sys/bus/platform/drivers') / DRIVER / 'bind').write_text('max77705-rgb\n')
        require(bound(), 'Selected-child bind did not complete')
    except Exception:
        subprocess.run(['rmmod', 'leds_g965n_trial'], check=False)
        (DEVICE / 'driver_override').write_text('\n')
        raise


def stop():
    if not bound():
        return
    for color in COLORS:
        (Path('/sys/class/leds') / (color + ':indicator') / 'brightness').write_text('0\n')
    (Path('/sys/bus/platform/drivers') / DRIVER / 'unbind').write_text('max77705-rgb\n')
    (DEVICE / 'driver_override').write_text('\n')
    subprocess.run(['rmmod', 'leds_g965n_trial'], check=True)


def registers():
    text = (DEVICE / 'g965n_led_registers').read_text()
    values = dict(re.findall(r'(enable|red|green|blue)=([0-9a-f]+)', text))
    require(set(values) == {'enable', *COLORS}, 'Unexpected LED readback')
    return {key: int(value, 16 if key == 'enable' else 10) for key, value in values.items()}


def test():
    require(bound(), 'Trial driver must already be started')
    nodes = [Path('/sys/class/leds') / (c + ':indicator') for c in COLORS]
    require(all(int((n / 'max_brightness').read_text()) == 1 and
                int((n / 'brightness').read_text()) == 0 for n in nodes), 'Unqualified cap or busy LED')
    white = registers()['enable'] & 3
    try:
        for channel, (color, node) in enumerate(zip(COLORS, nodes), 1):
            (node / 'brightness').write_text('1\n')
            time.sleep(.25)
            actual = registers()
            require(actual['enable'] == white | (1 << (channel * 2)) and actual[color] == 1,
                    'LED on readback mismatch')
            (node / 'brightness').write_text('0\n')
            time.sleep(.25)
            require(registers()['enable'] == white, 'LED off readback mismatch')
    finally:
        for node in nodes:
            (node / 'brightness').write_text('0\n')
    print('Three-channel low-current on/off readback passed; all LEDs off')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('start', 'stop', 'test'))
    p.add_argument('--confirm-sm-g965n-backed-up-led-trial', action='store_true', required=True)
    args = p.parse_args()
    preflight()
    {'start': start, 'stop': stop, 'test': test}[args.action]()


if __name__ == '__main__':
    main()

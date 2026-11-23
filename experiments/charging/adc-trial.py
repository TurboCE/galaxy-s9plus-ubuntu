#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""One guarded bounded ADC experiment, with owned modules removed in finally."""
import argparse
import hashlib
import importlib.util
import json
import mmap
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import time

ROOT = Path('/usr/local/lib/g965n-adc-trial')
MODULES = ('g965n-adc-v3', 'g965n-adc-board')
ABI = '45d68e3278f2498bb2d187c86b86c2803417d2c4dbcccbe096caf268dd6422e2'


def trusted(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise RuntimeError('Expected private root-owned regular file')
    return path.read_bytes()


def registers(page, offsets):
    with open('/dev/mem', 'rb', buffering=0) as source:
        with mmap.mmap(source.fileno(), 4096, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ, offset=page) as memory:
            return [struct.unpack_from('<I', memory, off)[0] for off in offsets]


def clocks():
    return registers(0x14202000, (0x18, 0x1c)) + registers(0x14203000, (0, 8, 12))


def active(name):
    return Path('/sys/module', name.replace('-', '_')).exists()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-sm-g965n-backed-up-adc-trial', required=True, action='store_true')
    parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    os.umask(0o077)
    guard_path = Path('/usr/local/lib/g965n-led-trial/led-control.py')
    trusted(guard_path)
    spec = importlib.util.spec_from_file_location('g965n_guard', guard_path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.preflight()
    pins = json.loads(trusted(ROOT/'pins.json'))
    if pins['module_symvers_sha256'] != ABI or set(pins['modules']) != set(MODULES):
        raise RuntimeError('Unqualified ADC build receipt')
    for name in MODULES:
        path = ROOT/(name+'.ko')
        if hashlib.sha256(trusted(path)).hexdigest() != pins['modules'][name]:
            raise RuntimeError('ADC module source/package pin mismatch')
        magic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(path)], text=True).strip()
        if magic != os.uname().release+' SMP preempt mod_unload aarch64' or active(name):
            raise RuntimeError('Module ABI changed or an existing module owner is present')
    if Path('/sys/bus/platform/devices/g965n-adc-v3-trial').exists():
        raise RuntimeError('Existing ADC owner preserved')
    battery = Path('/sys/class/power_supply/max170xx_battery')
    charger = Path('/sys/class/power_supply/max77705-charger')
    if (int((battery/'capacity').read_text()) < 5 or
            int((battery/'voltage_now').read_text()) < 3500000 or
            not 100 <= int((battery/'temp').read_text()) <= 350 or
            (charger/'online').read_text().strip() != '1' or
            '[auto]' not in (charger/'charge_behaviour').read_text()):
        raise RuntimeError('Insufficient stable battery/external power for a module trial')
    # A charger fault is precisely when diagnostic temperature data is useful.
    # This trial never enables/reinitializes charging or changes any limit.
    charger_health = (charger/'health').read_text().strip()
    before_clocks = clocks()
    if not all(v & (1 << 21) for v in before_clocks[:2]):
        raise RuntimeError('Firmware ADC access clocks are not held on')
    before_irq = (registers(0x10101000, (0xc08,))[0] >> 16) & 3
    if before_irq & 2:
        raise RuntimeError('ADC interrupt is not the observed level configuration')
    before_adc = registers(0x14230000, (0, 4, 0x10))
    if before_adc[0] & 5 or before_adc[2]:
        raise RuntimeError('Existing ADC conversion/interrupt owner preserved')
    receipt = Path(tempfile.mkdtemp(prefix='adc-trial-', dir='/var/lib/g965n-sensors'))
    (receipt/'before.json').write_text(json.dumps({'clocks': before_clocks, 'irq': before_irq,
                                                'adc': before_adc, 'pins': pins,
                                                'charger_health': charger_health}))
    attempted = []
    samples = []
    try:
        for name in MODULES:
            attempted.append(name)
            subprocess.run(['insmod', str(ROOT/(name+'.ko')), 'enable_g965n=1'],
                           check=True, timeout=10)
        nodes = [p for p in Path('/sys/bus/iio/devices').glob('iio:device*')
                 if (p/'name').read_text().strip() == 'g965n-adc-v3-trial']
        if len(nodes) != 1:
            raise RuntimeError('ADC driver did not register exactly one IIO provider')
        for _ in range(5):
            row = {'monotonic_ns': time.monotonic_ns()}
            for channel in (4, 1, 3, 11):
                row[str(channel)] = int((nodes[0]/f'in_voltage{channel}_raw').read_text())
            samples.append(row)
            time.sleep(.2)
    finally:
        (receipt/'samples.json').write_text(json.dumps(samples))
        for name in reversed(attempted):
            if active(name):
                subprocess.run(['rmmod', name.replace('-', '_')], check=True, timeout=10)
        after = {'clocks': clocks(), 'adc': registers(0x14230000, (0, 4, 0x10)),
                 'irq': (registers(0x10101000, (0xc08,))[0] >> 16) & 3}
        (receipt/'after.json').write_text(json.dumps(after))
        print(json.dumps({'samples': len(samples), 'modules_removed': all(not active(n) for n in MODULES),
                          'clocks_unchanged': after['clocks'] == before_clocks,
                          'controls_restored': after['adc'] == before_adc,
                          'irq_type_unchanged': after['irq'] == before_irq}), flush=True)
        if after['adc'] != before_adc:
            raise RuntimeError('ADC controls did not restore; preserve receipt for investigation')
    print(json.dumps({str(c): {'min': min(r[str(c)] for r in samples),
                               'max': max(r[str(c)] for r in samples)}
                      for c in (4, 1, 3, 11)}), flush=True)


if __name__ == '__main__':
    main()

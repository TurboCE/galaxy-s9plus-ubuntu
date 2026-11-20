#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Start Bluetooth on the checked native PCAL6524 and prepare Linux NFC."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


BASE = Path(__file__).resolve().parent
RUNTIME = Path('/run/g965n-native-nfc')
OWNER = RUNTIME / 'bluetooth-module'
SYS_MODULE = Path('/sys/module')
ADAPTER = Path('/sys/bus/platform/devices/10930000.i2c')
I2C_DEVICES = Path('/sys/bus/i2c/devices')


def run(*args):
    subprocess.run(args, check=True)


def load_modules():
    pins = json.loads((BASE / 'pins.json').read_text())
    for name in ('nfc', 'nci', 'zrn-bt', 'g965n-s3nrn82'):
        module = BASE / (name + '.ko')
        with module.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != pins[name]:
                raise RuntimeError(f'Module hash mismatch for {name}')
    for name in ('nfc', 'nci'):
        if not (SYS_MODULE / name).is_dir():
            run('/usr/sbin/insmod', str(BASE / (name + '.ko')))


def bind_expander():
    if (ADAPTER / 'driver').resolve(strict=True).name != 'exynos5-hsi2c':
        raise RuntimeError('Expected the native dedicated I2C controller')
    bus, = ADAPTER.glob('i2c-*')
    client = I2C_DEVICES / (bus.name.removeprefix('i2c-') + '-0022')
    if not client.exists():
        (bus / 'new_device').write_text('pcal6524 0x22\n')
    if ((client / 'name').read_text().strip() != 'pcal6524'
            or (client / 'driver').resolve(strict=True).name != 'pca953x'):
        raise RuntimeError('Expected the standard PCAL6524 GPIO driver')


def bind_nfc():
    if not (SYS_MODULE / 'g965n_s3nrn82').is_dir():
        run('/usr/sbin/insmod', str(BASE / 'g965n-s3nrn82.ko'))
    bus, = Path('/sys/bus/platform/devices/108e0000.i2c').glob('i2c-*')
    client = I2C_DEVICES / (bus.name.removeprefix('i2c-') + '-0027')
    if not client.exists():
        (bus / 'new_device').write_text('g965n-s3nrn82 0x27\n')
    if (client / 'driver').resolve(strict=True).name != 'g965n-s3nrn82':
        raise RuntimeError('Expected native S3NRN82 driver')


def start():
    if (SYS_MODULE / 'zrn_bt').exists() or (I2C_DEVICES / 'i2c-96').exists():
        raise RuntimeError('Bluetooth or its legacy I2C adapter is already loaded')
    bind_expander()
    load_modules()
    bind_nfc()
    run('/usr/sbin/insmod', str(BASE / 'zrn-bt.ko'), 'enable_g965n=1', 'native_expander=1')
    try:
        with OWNER.open('x'):
            pass
    except OSError:
        run('/usr/sbin/rmmod', 'zrn_bt')
        raise
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        ports = [Path('/dev') / tty.name for tty in Path('/sys/class/tty').glob('ttySAC*')
                 if 'exynos850-uart.0' in (tty / 'device').resolve().parts]
        if len(ports) == 1 and ports[0].is_char_device():
            os.execv('/usr/bin/btattach', ['btattach', '-B', str(ports[0]), '-P', 'bcm', '-S', '115200'])
        time.sleep(0.1)
    raise RuntimeError('Expected one Bluetooth UART device')


def stop():
    if OWNER.is_file():
        if (SYS_MODULE / 'zrn_bt').is_dir():
            run('/usr/sbin/rmmod', 'zrn_bt')
        OWNER.unlink()


if __name__ == '__main__':
    if sys.argv[1:] == ['start']:
        start()
    elif sys.argv[1:] == ['stop']:
        stop()
    else:
        raise SystemExit('Expected start or stop')

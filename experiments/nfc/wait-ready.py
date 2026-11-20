#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded readiness gate for neard after the shared NFC/Bluetooth loader."""
from pathlib import Path
import time


def ready():
    try:
        bus, = Path('/sys/bus/platform/devices/108e0000.i2c').glob('i2c-*')
        client = Path('/sys/bus/i2c/devices') / (bus.name.removeprefix('i2c-') + '-0027')
        if (client / 'driver').resolve(strict=True).name != 'g965n-s3nrn82':
            return False
        parent = client.resolve(strict=True)
        return any(parent in radio.resolve(strict=True).parents
                   for radio in Path('/sys/class/nfc').glob('nfc*'))
    except (OSError, ValueError):
        return False


if __name__ == '__main__':
    deadline = time.monotonic() + 30
    while not ready():
        if time.monotonic() >= deadline:
            raise SystemExit('Native G965N NFC radio did not become ready in 30 seconds')
        time.sleep(0.1)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only bounded real ALS/backlight observation; no sensor/control writes."""
import argparse
import json
import os
from pathlib import Path
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, choices=range(1, 601), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stop-file', type=Path)
    args = parser.parse_args()
    devices = [p for p in Path('/sys/bus/iio/devices').glob('iio:device*')
               if p.joinpath('name').read_text().strip() == 'g965n-ssp-light']
    if len(devices) != 1:
        raise RuntimeError('Expected one real G965N light device')
    light = devices[0]/'in_illuminance_input'
    backlight = Path('/sys/class/backlight/g965n-panel-aor')
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    end = time.monotonic() + args.seconds
    with os.fdopen(fd, 'w') as stream:
        while time.monotonic() < end:
            if args.stop_file and args.stop_file.exists():
                break
            row = {'monotonic_s': time.monotonic()}
            try:
                row.update(lux=float(light.read_text()),
                           requested=int(backlight.joinpath('brightness').read_text()),
                           actual=int(backlight.joinpath('actual_brightness').read_text()),
                           bl_power=int(backlight.joinpath('bl_power').read_text()))
            except OSError as error:
                # A missing/stale device is not a zero-lux measurement.
                row.update(unavailable=True, errno=error.errno)
            stream.write(json.dumps(row) + '\n')
            stream.flush()
            time.sleep(.5)
    print('Bounded ALS/backlight observation finished; output remains private')


if __name__ == '__main__':
    main()

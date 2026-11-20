#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build a pinned native #48 LED module in a new directory; never touches a phone."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel-source', type=Path, required=True)
    p.add_argument('--kernel-out', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--named-regmap', action='store_true', help='Apply reviewed unique RGB regmap identity')
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    pins = json.loads((here / 'LED_TRIAL.json').read_text())
    source = args.kernel_source.resolve()
    out = args.kernel_out.resolve()
    target = args.output.resolve()
    original = source / 'drivers/leds/leds-max77705.c'
    patch = here / '0004-g965n-low-current-led-trial.patch'
    if (digest(original) != pins['input_sha256'] or
            digest(patch) != pins['patch_sha256'] or
            digest(out / 'Module.symvers') != pins['module_symvers_sha256']):
        raise RuntimeError('Unreviewed LED source, patch or module ABI')
    target.mkdir(mode=0o700)
    staged = target / 'drivers/leds/leds-max77705.c'
    staged.parent.mkdir(parents=True)
    staged.write_bytes(original.read_bytes())
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(target),
                    '-i', str(patch)], check=True)
    if digest(staged) != pins['output_sha256']:
        raise RuntimeError('Unexpected patched source')
    if args.named_regmap:
        named = json.loads((here / 'LED_REGMAP_NAME.json').read_text())
        extra = here / '0007-g965n-rgb-regmap-name.patch'
        if digest(staged) != named['input_sha256'] or digest(extra) != named['patch_sha256']:
            raise RuntimeError('Unreviewed RGB regmap-name source/patch')
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(target), '-i', str(extra)], check=True)
        if digest(staged) != named['output_sha256']:
            raise RuntimeError('Unexpected named regmap output')
    (target / 'leds-g965n-trial.c').write_bytes(staged.read_bytes())
    (target / 'Makefile').write_text('obj-m += leds-g965n-trial.o\n')
    subprocess.run(['make', '-s', '-C', str(source), 'O=' + str(out),
                    'ARCH=arm64', 'CROSS_COMPILE=aarch64-linux-gnu-',
                    'M=' + str(target), 'KCFLAGS=-Werror', 'modules'], check=True)
    dependency = out / 'drivers/leds/led-class-multicolor.ko'
    (target / dependency.name).write_bytes(dependency.read_bytes())
    modules = {name: digest(target / name)
               for name in ('leds-g965n-trial.ko', 'led-class-multicolor.ko')}
    (target / 'pins.json').write_text(json.dumps(modules, indent=2) + '\n')
    print('LED modules built; no device writes; hardware validation is separate')


if __name__ == '__main__':
    main()

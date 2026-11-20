#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reproduce native #48 PWM/motor modules and bounded test tools; never flashes."""
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
    p.add_argument('--idle-power', action='store_true', help='Apply the separate reviewed persistent-client idle fix')
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    pins = json.loads((here / 'HAPTIC_TRIAL.json').read_text())
    source, out, target = (p.resolve() for p in (args.kernel_source, args.kernel_out, args.output))
    original = source / 'drivers/input/misc/max77693-haptic.c'
    patch = here / '0005-g965n-haptic-duty-limit.patch'
    if (digest(original) != pins['input_sha256'] or digest(patch) != pins['patch_sha256'] or
            digest(out / 'Module.symvers') != pins['module_symvers_sha256']):
        raise RuntimeError('Unreviewed haptic source, patch or kernel ABI')
    for name, expected in pins['board_sources'].items():
        if digest(here / name) != expected:
            raise RuntimeError('Board/test source differs from reviewed trial')
    target.mkdir(mode=0o700)
    staged = target / 'drivers/input/misc/max77693-haptic.c'
    staged.parent.mkdir(parents=True)
    staged.write_bytes(original.read_bytes())
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(target), '-i', str(patch)], check=True)
    if digest(staged) != pins['output_sha256']:
        raise RuntimeError('Unexpected haptic patch output')
    if args.idle_power:
        idle = json.loads((here / 'HAPTIC_IDLE_POWER.json').read_text())
        idle_patch = here / '0006-g965n-haptic-idle-power.patch'
        if digest(staged) != idle['input_sha256'] or digest(idle_patch) != idle['patch_sha256']:
            raise RuntimeError('Unreviewed idle-power input or patch')
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(target),
                        '-i', str(idle_patch)], check=True)
        if digest(staged) != idle['output_sha256']:
            raise RuntimeError('Unexpected idle-power patch output')
    (target / 'g965n-haptic-trial.c').write_bytes(staged.read_bytes())
    for name in ('g965n-pwm-board.c', 'g965n-haptic-board.c'):
        (target / name).write_bytes((here / name).read_bytes())
    (target / 'Makefile').write_text('obj-m += g965n-pwm-board.o g965n-haptic-board.o g965n-haptic-trial.o\n')
    subprocess.run(['make', '-s', '-C', str(source), 'O=' + str(out), 'ARCH=arm64',
                    'CROSS_COMPILE=aarch64-linux-gnu-', 'M=' + str(target),
                    'KCFLAGS=-Werror', 'modules'], check=True)
    (target / 'ff-memless.ko').write_bytes((out / 'drivers/input/ff-memless.ko').read_bytes())
    for name, output in [('haptic-test.c', 'haptic-test'), ('measure-pwm-counter.c', 'measure-pwm-counter'),
                         ('read-fvmap32.c', 'read-fvmap32'),
                         ('read-motor-pins32.c', 'read-motor-pins32')]:
        subprocess.run(['aarch64-linux-gnu-gcc', '-O2', '-Wall', '-Wextra', '-Werror',
                        *(['-DG965N_HAPTIC_IDLE_BOOST=0'] if args.idle_power and name == 'haptic-test.c' else []),
                        str(here / name), '-o', str(target / output)], check=True)
    module_names = ('g965n-pwm-board.ko', 'g965n-haptic-board.ko', 'g965n-haptic-trial.ko', 'ff-memless.ko')
    (target / 'pins.json').write_text(json.dumps({n: digest(target / n) for n in module_names}, indent=2) + '\n')
    program_names = ('haptic-test', 'measure-pwm-counter', 'read-fvmap32', 'read-motor-pins32')
    (target / 'program-pins.json').write_text(json.dumps({n: digest(target / n) for n in program_names}, indent=2) + '\n')
    print('Haptic modules and bounded diagnostics built; no device writes')


if __name__ == '__main__':
    main()

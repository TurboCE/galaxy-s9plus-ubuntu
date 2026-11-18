#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded native GPU qualification; never flashes or changes system settings.

Keep output PRIVATE: kernel logs and GPU dumps can contain application data.
A benchmark score alone is not a pass. Reboot testing is separate.
"""
import argparse
import fcntl
import glob
import json
import os
from pathlib import Path
import re
import subprocess
import time

FAULT = re.compile(r'panfrost.*(?:timeout|fault|failed|error|WARNING)|WARNING:.*panfrost|flip did not latch|shadow update stuck', re.I)


def journal(*args):
    return subprocess.check_output(['journalctl', '-k', '-b', '--no-pager', *args], text=True, stderr=subprocess.STDOUT)


def run(command, environment, timeout):
    try:
        result = subprocess.run(command, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired as error:
        output = error.stdout or b''
        if isinstance(output, bytes):
            output = output.decode(errors='replace')
        return 124, output + '\nQUALIFICATION_TIMEOUT\n'


def snapshot():
    settings = {}
    for pattern in ['/sys/bus/platform/devices/17500000.gpu/power/control',
                    '/sys/bus/platform/devices/17500000.gpu/power/autosuspend_delay_ms',
                    '/sys/class/devfreq/*.gpu/governor', '/sys/class/devfreq/*.gpu/min_freq',
                    '/sys/class/devfreq/*.gpu/max_freq', '/sys/module/s9p_g3d/parameters/*',
                    '/sys/module/s9p_g3d_pd/parameters/*', '/sys/module/panfrost/parameters/s9p_*']:
        for name in glob.glob(pattern):
            try:
                settings[name] = Path(name).read_text().strip()
            except OSError:
                pass
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New private directory outside published artifacts')
    parser.add_argument('--readback', type=Path, required=True, help='Compiled gpu-readback.c')
    parser.add_argument('--mesa-debug', choices=['normal', 'noafbc', 'nocrc', 'sync'], default='normal')
    parser.add_argument('--cooldown', type=int, choices=range(0, 31), default=5)
    args = parser.parse_args()
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected the native star2lte handset')
    if not args.readback.is_file():
        raise SystemExit('Compile gpu-readback.c first')
    runtime = Path('/run/user') / str(os.getuid())
    if not (runtime / 'wayland-0').exists():
        raise SystemExit('An active local Wayland session is required')
    with (runtime / 'g965n-gpu-validation.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another GPU validation is running; do not overlap comparisons')
        cursor_text = journal('-n', '0', '--show-cursor')
        match = re.search(r'^-- cursor: (.+)$', cursor_text, re.M)
        if not match:
            raise SystemExit('Cannot establish kernel-log boundary')
        os.umask(0o077)
        args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
        env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY='wayland-0')
        env.pop('PAN_MESA_DEBUG', None)
        if args.mesa_debug != 'normal':
            env['PAN_MESA_DEBUG'] = args.mesa_debug
        settings = snapshot()
        results = {}
        commands = [('readback', [str(args.readback.resolve())], 30),
                    ('scenes', ['glmark2-es2-wayland', '--size', '512x512', '--benchmark', ':duration=1'], 90)]
        for name, command, timeout in commands:
            code, output = run(command, env, timeout)
            (args.output / (name + '.log')).write_text(output)
            hardware = bool(re.search(r'(?:renderer=|GL_RENDERER:).*Mali', output))
            complete = ('PASS frames=100' in output if name == 'readback' else
                        'glmark2 Score:' in output and len(re.findall(r'^\[[^\]]+\]', output, re.M)) == 33)
            results[name] = {'exit': code, 'physical_mali': hardware, 'complete': complete}
        time.sleep(args.cooldown)
        delta = journal('--after-cursor', match[1])
        (args.output / 'kernel.log').write_text(delta)
        faults = [line for line in delta.splitlines() if FAULT.search(line)]
        passed = all(r['exit'] == 0 and r['physical_mali'] and r['complete'] for r in results.values()) and not faults
        receipt = {'kernel': os.uname().release, 'kernel_version': os.uname().version,
                   'mesa_debug': args.mesa_debug, 'settings_before': settings,
                   'settings_after': snapshot(), 'tests': results,
                   'kernel_fault_lines': len(faults), 'passed': passed,
                   'scope': 'bounded rendering only; not reboot, browser, video decoding or long-term stability'}
        (args.output / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))
        raise SystemExit(0 if passed else 2)


if __name__ == '__main__':
    main()

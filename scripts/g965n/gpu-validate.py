#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded native GPU qualification; never flashes or changes persistent system settings.

Keep output PRIVATE: kernel logs and GPU dumps can contain application data.
A benchmark score alone is not a pass. Reboot testing is separate.
"""
import argparse
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import fcntl
import glob
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time

FAULT = re.compile(r'panfrost.*(?:timeout|fault|failed|error|WARNING)|WARNING:.*panfrost|flip did not latch|shadow update stuck|swiotlb buffer is full|vblank wait timed out|flip_done timed out', re.I)
TARGETED = (
    ('buffer', 'columns=200:interleave=true:update-dispersion=0.9:update-fraction=0.5:update-method=map:duration=8'),
    ('function', 'fragment-complexity=low:fragment-steps=5:duration=8'),
    ('loop', 'fragment-loop=false:fragment-steps=5:vertex-steps=5:duration=8'),
)


def scene_result(output, profile):
    rows = re.findall(r'^\[([^\]]+)\][ \t]*(.*):[ \t]*FPS:[ \t]*([0-9.]+)'
                      r'[ \t]+FrameTime:[ \t]*([0-9.]+)[ \t]+ms[ \t]*$', output, re.M)
    announced = len(re.findall(r'^\[[^\]]+\]', output, re.M))

    def positive(row):
        try:
            values = [float(value) for value in row[2:]]
            return all(math.isfinite(value) and value > 0 for value in values)
        except ValueError:
            return False

    if profile == 'full':
        return {'complete': 'glmark2 Score:' in output and announced == len(rows) == 33
                            and all(positive(row) for row in rows),
                'expected_scene_count': 33, 'observed_scene_count': announced,
                'completed_scene_count': len(rows)}
    if profile != 'targeted':
        raise ValueError('Unknown GPU profile')
    complete = len(rows) == announced == len(TARGETED) and 'glmark2 Score:' in output
    for (name, options), row in zip(TARGETED, rows):
        actual = dict(part.split('=', 1) for part in row[1].split(':') if '=' in part)
        expected = dict(part.split('=', 1) for part in options.split(':'))
        complete = complete and positive(row) and row[0] == name and all(actual.get(k) == v for k, v in expected.items())
    return {'complete': bool(complete), 'expected_scene_count': len(TARGETED),
            'expected_scenes': [name + ':' + options for name, options in TARGETED],
            'observed_scene_count': announced, 'completed_scene_count': len(rows),
            'observed_scenes': [row[0] for row in rows]}


def commands_for(profile, readback, size, fifo=False, fullscreen=False):
    surface = ['--fullscreen'] if fullscreen else ['--size', size]
    if profile == 'full':
        commands = [('readback', [str(readback.resolve())], 30),
                    ('scenes', ['glmark2-es2-wayland', *surface, '--benchmark', ':duration=1'], 90)]
    elif profile == 'targeted':
        command = ['glmark2-es2-wayland', *surface]
        for name, options in TARGETED:
            command += ['-b', name + ':' + options]
        commands = [('targeted', command, 45)]
    else:
        raise ValueError('Unknown GPU profile')
    if fifo:
        commands.append(('fifo', ['glmark2-es2-wayland', *surface, '--swap-mode', 'fifo',
            '-b', 'build:duration=4', '-b', 'texture:duration=4', '-b', 'ideas:duration=4'], 30))
    return commands


def fifo_result(output):
    frames = re.findall(r'^\[(build|texture|ideas)\].*FPS:\s*([0-9.]+)', output, re.M)
    complete = (len(frames) == 3 and {name for name, _ in frames} == {'build', 'texture', 'ideas'}
                and 'glmark2 Score:' in output)
    fps = {name: float(value) for name, value in frames}
    # This port currently exposes a single fixed 60Hz mode. A 31fps FIFO
    # result must not pass just because an unconstrained score is high.
    return {'complete': complete, 'fps': fps,
            'cadence_pass': complete and all(value >= 54.0 for value in fps.values())}


def display_awake(bus):
    from gi.repository import Gio, GLib
    result = bus.call_sync('org.gnome.Mutter.DisplayConfig', '/org/gnome/Mutter/DisplayConfig',
        'org.freedesktop.DBus.Properties', 'Get',
        GLib.Variant('(ss)', ('org.gnome.Mutter.DisplayConfig', 'PowerSaveMode')),
        None, Gio.DBusCallFlags.NONE, 5000, None)
    return result.unpack()[0] == 0


def screen_unlocked(bus):
    from gi.repository import Gio
    return not bus.call_sync('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver',
        'org.gnome.ScreenSaver', 'GetActive', None, None,
        Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]


@contextmanager
def hold_desktop_awake():
    # Temporary application inhibitor, released even when validation fails.
    # Never rewrite the owner's idle/suspend preferences or bypass Shell APIs.
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    if not display_awake(bus):
        raise SystemExit('Display is asleep; wake it before GPU qualification')
    if not screen_unlocked(bus):
        raise SystemExit('Session is locked; unlock it before GPU qualification')
    overview = bus.call_sync('org.gnome.Shell', '/org/gnome/Shell',
        'org.freedesktop.DBus.Properties', 'Get',
        GLib.Variant('(ss)', ('org.gnome.Shell', 'OverviewActive')),
        None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    if overview:
        raise SystemExit('Close the application overview before GPU qualification')
    service = ('org.gnome.SessionManager', '/org/gnome/SessionManager', 'org.gnome.SessionManager')
    cookie = bus.call_sync(*service, 'Inhibit',
        GLib.Variant('(susu)', ('g965n-gpu-validation', 0, 'Bounded GPU qualification', 8)),
        None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    try:
        yield bus
    finally:
        bus.call_sync(*service, 'Uninhibit', GLib.Variant('(u)', (cookie,)),
            None, Gio.DBusCallFlags.NONE, 5000, None)


def journal(*args):
    return subprocess.check_output(['journalctl', '-k', '-b', '--no-pager', *args], text=True, stderr=subprocess.STDOUT)


def run_timed(command, environment, timeout, timeline, name, protocol=None):
    """Nonblocking line capture with one deadline, including silent/partial output.

    A fresh process group lets cleanup also reap the direct child when a
    descendant retains stdout. No reader thread can survive a timed-out command.
    """
    output, pending = bytearray(), bytearray()
    process = None
    finished = False
    code = 124
    deadline = time.monotonic() + timeout
    with ExitStack() as stack:
        stream = stack.enter_context(timeline.open('a', encoding='utf-8')) if timeline else None
        protocol_stream = stack.enter_context(protocol.open('xb')) if protocol else None

        def record(event, **fields):
            if stream is None:
                return
            row = {'command': name, 'event': event,
                   'utc': datetime.now(timezone.utc).isoformat(),
                   'monotonic_ns': time.monotonic_ns(), **fields}
            stream.write(json.dumps(row) + '\n'); stream.flush()

        try:
            record('start')
            process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE if protocol else subprocess.STDOUT,
                start_new_session=True)
            os.set_blocking(process.stdout.fileno(), False)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
                if protocol:
                    os.set_blocking(process.stderr.fileno(), False)
                    selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, timeout)
                    events = selector.select(remaining)
                    if not events:
                        raise subprocess.TimeoutExpired(command, timeout)
                    for key, _ in events:
                        data = os.read(key.fd, 65536)
                        if not data:
                            selector.unregister(key.fileobj)
                            continue
                        if key.data == 'stderr':
                            protocol_stream.write(data)
                            continue
                        output.extend(data); pending.extend(data)
                        while b'\n' in pending:
                            if time.monotonic() >= deadline:
                                raise subprocess.TimeoutExpired(command, timeout)
                            line, _, rest = pending.partition(b'\n')
                            pending[:] = rest
                            record('line', line=line.decode(errors='replace'), partial=False)
                code = process.wait(timeout=max(0, deadline - time.monotonic()))
                finished = True
        except subprocess.TimeoutExpired:
            code = 124
        finally:
            if process is not None:
                if not finished:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait()
                process.stdout.close()
                if process.stderr is not None:
                    process.stderr.close()
        if pending:
            record('line', line=pending.decode(errors='replace'), partial=True)
        record('finish', exit=code, timed_out=not finished)
    return code, output.decode(errors='replace') + ('' if finished else '\nQUALIFICATION_TIMEOUT\n')


def run(command, environment, timeout, timeline=None, name=None, protocol=None):
    if timeline is not None or protocol is not None:
        command_name = name or Path(command[0]).name
        # glmark2 uses stdio; line buffering makes receipt times meaningful.
        if Path(command[0]).name == 'glmark2-es2-wayland':
            if protocol is not None:
                # An explicit per-child override; never change the caller's
                # environment or enable tracing on readback/other commands.
                environment = dict(environment, WAYLAND_DEBUG='client')
            command = ['stdbuf', '-oL', '-eL', *command]
        return run_timed(command, environment, timeout, timeline, command_name, protocol)
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
                    '/sys/module/s9p_g3d_pd/parameters/*', '/sys/module/panfrost/parameters/s9p_*',
                    '/sys/module/s9p_decon/parameters/*']:
        for name in glob.glob(pattern):
            try:
                settings[name] = Path(name).read_text().strip()
            except OSError:
                pass
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New private directory outside published artifacts')
    parser.add_argument('--readback', type=Path, help='Compiled gpu-readback.c; required for the full profile')
    parser.add_argument('--profile', choices=['full', 'targeted'], default='full',
                        help='Full qualification or the three bounded native-size timeout reproductions')
    parser.add_argument('--timeline', action='store_true', help='Write private per-command line timing to timeline.jsonl')
    parser.add_argument('--wayland-protocol', action='store_true',
                        help='Capture glmark child stderr/Wayland protocol separately; diagnostic only')
    parser.add_argument('--mesa-debug', choices=['normal', 'noafbc', 'nocrc', 'nocrc,noafbc', 'sync'], default='normal')
    parser.add_argument('--fifo', action='store_true', help='Also require near-60Hz FIFO presentation in three bounded scenes')
    parser.add_argument('--size', choices=['512x512', '720x1480', '1440x2960'], default='512x512',
                        help='Requested benchmark surface; readback remains its independent fixed-size check')
    parser.add_argument('--fullscreen', action='store_true',
                        help='Ask glmark for fullscreen instead of --size; verify actual buffer dimensions separately')
    parser.add_argument('--cooldown', type=int, choices=range(0, 31), default=5)
    args = parser.parse_args()
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected the native star2lte handset')
    if args.profile == 'full' and (args.readback is None or not args.readback.is_file()):
        raise SystemExit('Compile gpu-readback.c first')
    runtime = Path('/run/user') / str(os.getuid())
    if not (runtime / 'wayland-0').exists():
        raise SystemExit('An active local Wayland session is required')
    with (runtime / 'g965n-gpu-validation.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another GPU validation is running; do not overlap comparisons')
        with hold_desktop_awake() as desktop_bus:
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
            commands = commands_for(args.profile, args.readback, args.size, args.fifo, args.fullscreen)
            for name, command, timeout in commands:
                timeline = args.output / 'timeline.jsonl' if args.timeline else None
                protocol = (args.output / (name + '.wayland.log') if args.wayland_protocol
                            and Path(command[0]).name == 'glmark2-es2-wayland' else None)
                code, output = run(command, env, timeout, timeline, name, protocol)
                (args.output / (name + '.log')).write_text(output)
                hardware = bool(re.search(r'(?:renderer=|GL_RENDERER:).*Mali', output))
                complete = 'PASS frames=100' in output if name == 'readback' else False
                results[name] = {'exit': code, 'physical_mali': hardware, 'complete': complete}
                if protocol is not None:
                    results[name]['wayland_protocol_log'] = protocol.name
                if name in ('scenes', 'targeted'):
                    results[name].update(scene_result(output, args.profile))
                surface = re.search(r'^\s*Surface Size:\s*(.+)$', output, re.M)
                if surface:
                    results[name]['reported_surface'] = surface[1].strip()
                if name == 'fifo':
                    results[name].update(fifo_result(output))
            time.sleep(args.cooldown)
            delta = journal('--after-cursor', match[1])
            (args.output / 'kernel.log').write_text(delta)
            faults = [line for line in delta.splitlines() if FAULT.search(line)]
            awake = display_awake(desktop_bus)
            unlocked = screen_unlocked(desktop_bus)
            passed = awake and unlocked and all(r['exit'] == 0 and r['physical_mali'] and r['complete'] and r.get('cadence_pass', True) for r in results.values()) and not faults
            receipt = {'kernel': os.uname().release, 'kernel_version': os.uname().version,
                       'profile': args.profile, 'line_timeline': args.timeline,
                       'wayland_protocol': {'requested': args.wayland_protocol,
                           'scope': 'Glmark child stderr only; presented wl_buffer modifier is not necessarily the render-target modifier; protocol tracing adds overhead'},
                       'mesa_debug': args.mesa_debug,
                       'requested_surface': 'fullscreen' if args.fullscreen else args.size,
                       'fullscreen': args.fullscreen, 'display_awake_after': awake,
                       'desktop_unlocked_after': unlocked,
                       'temporary_idle_inhibitor': True, 'settings_before': settings,
                       'settings_after': snapshot(), 'tests': results,
                       'kernel_fault_lines': len(faults), 'passed': passed,
                       'scope': 'bounded rendering only; not reboot, browser, video decoding or long-term stability'}
            (args.output / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
            print(json.dumps(receipt, indent=2))
            raise SystemExit(0 if passed else 2)


if __name__ == '__main__':
    main()

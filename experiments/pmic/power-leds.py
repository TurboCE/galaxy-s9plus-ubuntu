#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bind guarded G965N LEDs to existing battery triggers; never changes charging."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import stat
import sys

ROOT = Path('/usr/local/lib/g965n-led-trial')
STATE = Path('/run/g965n-power-leds.json')
LOCK = Path('/run/g965n-power-leds.lock')
POLICY = {'red': 'max170xx_battery-charging', 'green': 'max170xx_battery-full'}


def trusted(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise RuntimeError('Expected private root-owned policy state/source')
    return path.read_bytes()


def preflight():
    path = ROOT / 'led-control.py'
    trusted(path)
    spec = importlib.util.spec_from_file_location('g965n_led_guard', path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard.preflight()
    if not guard.bound():
        raise RuntimeError('Qualified LED driver is not bound')
    nodes = {color: Path('/sys/class/leds') / (color + ':indicator') for color in POLICY}
    for node in nodes.values():
        if not node.resolve().is_relative_to(guard.DEVICE.resolve()):
            raise RuntimeError('Foreign LED parent preserved')
        if (node / 'max_brightness').read_text().strip() != '1':
            raise RuntimeError('Expected qualified low-current LED cap')
    return nodes


def selected(node):
    match = re.search(r'\[([^]]+)\]', (node / 'trigger').read_text())
    if not match:
        raise RuntimeError('LED trigger selection unavailable')
    return match.group(1)


def saved():
    value = json.loads(trusted(STATE))
    if (set(value) != {'boot', 'original'} or
            value['boot'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip() or
            set(value['original']) != set(POLICY) or
            any(v != {'trigger': 'none', 'brightness': 0} for v in value['original'].values())):
        raise RuntimeError('Unowned LED policy state preserved')
    return value


def stop(nodes):
    if not STATE.exists():
        return
    original = saved()['original']
    for color, node in nodes.items():
        if selected(node) == POLICY[color]:
            (node / 'trigger').write_text(original[color]['trigger'] + '\n')
            (node / 'brightness').write_text(str(original[color]['brightness']) + '\n')
        # A user's later trigger selection takes ownership; preserve it.
    STATE.unlink()


def start(nodes):
    if STATE.exists():
        saved()
        if all(selected(node) == POLICY[color] for color, node in nodes.items()):
            return
        raise RuntimeError('Existing policy changed; preserve manual LED selection')
    original = {color: {'trigger': selected(node), 'brightness': int((node / 'brightness').read_text())}
                for color, node in nodes.items()}
    if any(v != {'trigger': 'none', 'brightness': 0} for v in original.values()):
        raise RuntimeError('Existing LED use preserved')
    for color, node in nodes.items():
        if POLICY[color] not in (node / 'trigger').read_text().replace('[', '').replace(']', '').split():
            raise RuntimeError('Native battery LED trigger unavailable')
    value = {'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'original': original}
    fd = os.open(STATE, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        for color, node in nodes.items():
            (node / 'trigger').write_text(POLICY[color] + '\n')
            if selected(node) != POLICY[color]:
                raise RuntimeError('LED trigger readback mismatch')
    except Exception:
        stop(nodes)
        raise


def follow_battery(nodes, shutdown):
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    path = bus.call_sync('org.freedesktop.UPower', '/org/freedesktop/UPower',
                         'org.freedesktop.UPower', 'GetDisplayDevice', None, None,
                         0, 3000, None).unpack()[0]
    proxy = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.DO_NOT_AUTO_START,
                                  None, 'org.freedesktop.UPower', path,
                                  'org.freedesktop.UPower.Device', None)
    loop = GLib.MainLoop()
    shutdown['loop'] = loop
    failures = []

    def changed(_proxy, properties, _invalidated):
        if 'State' not in properties.unpack():
            return
        try:
            if not all(selected(node) == POLICY[color] for color, node in nodes.items()):
                loop.quit()  # A manual/notification owner superseded this policy.
                return
            # A net-current reversal may not raise a fuel-gauge hardware IRQ.
            # React to UPower's real state update, then let the native trigger
            # activation sample the kernel battery status and refresh both LEDs.
            red = nodes['red'] / 'trigger'
            red.write_text('none\n')
            red.write_text(POLICY['red'] + '\n')
        except Exception as error:
            failures.append(error)
            loop.quit()

    proxy.connect('g-properties-changed', changed)
    address = os.environ.get('NOTIFY_SOCKET')
    if address:
        if address.startswith('@'):
            address = '\0' + address[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as notify:
            notify.connect(address)
            notify.sendall(b'READY=1')
    if not shutdown['requested']:
        loop.run()
    if failures:
        raise RuntimeError('Battery LED state refresh failed') from failures[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'stop', 'run'))
    parser.add_argument('--confirm-sm-g965n-backed-up-power-leds', required=True, action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    shutdown = {'requested': False, 'loop': None}

    def terminate(*_):
        shutdown['requested'] = True
        if shutdown['loop'] is not None:
            shutdown['loop'].quit()

    if args.action == 'run':
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, terminate)
    nodes = preflight()
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'run':
            try:
                if not shutdown['requested']:
                    start(nodes)
                    follow_battery(nodes, shutdown)
            finally:
                stop(nodes)
        else:
            {'start': start, 'stop': stop}[args.action](nodes)
    print('Battery LED policy ' + ('enabled' if args.action == 'start' else 'released'))


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(78)

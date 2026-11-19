#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Own a standby IPv4 route only while the exact G965N RIL lease is live."""
import argparse
import fcntl
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import time

DEVICE = 'rmnet0'
METRIC = 20000
LAB_UNIT = 'g965n-ril-lab-test.service'


def command(*argv):
    return subprocess.check_output(argv, text=True, timeout=3)


def ip_json(*argv):
    return json.loads(command('ip', '-4', '-j', *argv))


def defaults():
    return ip_json('route', 'show', 'default')


def read_lease(path, now):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'rb') as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o077:
            raise RuntimeError('Unsafe IPv4 lease file')
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise RuntimeError('Oversized IPv4 lease')
    record = json.loads(raw)
    expiry = record['valid_until']
    # The publisher can rename a renewed lease while this reader opens it.
    if type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry > now + 6:
        raise RuntimeError('Invalid IPv4 lease expiry')
    if expiry <= now:
        return None
    generation = record['generation']
    cfg = record['config']
    if type(generation) is not int or generation < 1 or type(cfg['cid']) is not int or cfg['cid'] != 1:
        raise RuntimeError('Unexpected modem context or generation')
    if type(cfg['mtu']) is not int or not 576 <= cfg['mtu'] <= 1500:
        raise RuntimeError('Unexpected modem MTU')
    if not isinstance(cfg['dns4'], list) or not 1 <= len(cfg['dns4']) <= 2:
        raise RuntimeError('Unexpected modem DNS list')
    addresses = [ipaddress.IPv4Address(text) for text in [cfg['ipv4'], *cfg['dns4']]]
    for address in addresses:
        if (address.is_loopback or address.is_multicast or address.is_unspecified
                or address.is_link_local or int(address) == 0xffffffff):
            raise RuntimeError('Unexpected modem address')
    return generation, str(addresses[0]), tuple(map(str, addresses[1:])), cfg['mtu']


class Route:
    def __init__(self, lease):
        self.generation, address, self.servers, self.mtu = lease
        self.address = address + '/32'
        self.modem_default = ('default', 'dev', DEVICE, 'src', address, 'metric', str(METRIC))
        self.original, = ip_json('link', 'show', 'dev', DEVICE)
        links = json.loads(command('ip', '-j', 'address', 'show', 'dev', DEVICE))
        if (self.original['link_type'] != 'ppp' or 'UP' in self.original['flags']
                or len(links) != 1 or links[0]['addr_info']
                or any(route['dev'] == DEVICE for route in defaults())):
            raise RuntimeError('Expected an idle unmanaged modem interface')
        for kind in ('dns', 'domain'):
            _, sep, settings = command('resolvectl', kind, DEVICE).partition(':')
            if not sep or settings.strip():
                raise RuntimeError('Preserve existing per-link resolver settings')
        self.up = self.address_added = self.default_added = self.dns_selected = False
        self.dns_touched = False

    def install(self):
        command('ip', 'link', 'set', 'dev', DEVICE, 'mtu', str(self.mtu), 'up')
        self.up = True
        command('ip', 'address', 'add', self.address, 'dev', DEVICE)
        self.address_added = True
        command('ip', '-4', 'route', 'add', *self.modem_default)
        self.default_added = True
        print(json.dumps({'lte_route_active': self.generation}), flush=True)

    def sync_dns(self):
        link, = ip_json('link', 'show', 'dev', DEVICE)
        if link['ifindex'] != self.original['ifindex'] or 'UP' not in link['flags']:
            raise RuntimeError('Modem interface changed')
        rows = defaults()
        if not any(row['dev'] == DEVICE and row.get('metric') == METRIC for row in rows):
            raise RuntimeError('Modem default route disappeared')
        preferred = min(rows, key=lambda row: row.get('metric', 0))['dev']
        want_dns = preferred == DEVICE
        if want_dns == self.dns_selected:
            return
        if want_dns:
            self.dns_touched = True
            command('resolvectl', 'dns', DEVICE, *self.servers)
            command('resolvectl', 'domain', DEVICE, '~.')
            command('resolvectl', 'default-route', DEVICE, 'yes')
        else:
            command('resolvectl', 'revert', DEVICE)
            self.dns_touched = False
        self.dns_selected = want_dns
        print(json.dumps({'lte_default_dns': want_dns}), flush=True)

    def close(self):
        if not self.up:
            return
        try:
            link, = ip_json('link', 'show', 'dev', DEVICE)
        except subprocess.CalledProcessError:
            return  # Kernel has removed this link and its settings.
        if link['ifindex'] != self.original['ifindex']:
            return  # The new link is not ours.
        cleanup = []
        if self.dns_touched:
            cleanup.append(('resolvectl', 'revert', DEVICE))
        if self.default_added:
            cleanup.append(('ip', '-4', 'route', 'del', *self.modem_default))
        if self.address_added:
            cleanup.append(('ip', 'address', 'del', self.address, 'dev', DEVICE))
        cleanup.append(('ip', 'link', 'set', 'dev', DEVICE, 'mtu', str(self.original['mtu']), 'down'))
        failed = False
        for args in cleanup:
            try:
                command(*args)
            except subprocess.SubprocessError:
                failed = True
        print(json.dumps({'lte_route_removed': self.generation, 'cleanup_ok': not failed}), flush=True)
        if failed:
            raise RuntimeError('Incomplete LTE route cleanup')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--invocation', required=True)
    parser.add_argument('--confirm-guarded-g965n-route', action='store_true', required=True)
    args = parser.parse_args()
    if (os.geteuid() != 0 or not re.fullmatch(r'[a-f0-9]{32}', args.invocation)
            or b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0')
            or not Path('/sys/module/g965n_modem').is_dir()):
        raise SystemExit('Expected guarded G965N modem and exact RIL invocation')
    os.umask(0o077)
    lock = os.open('/run/lock/g965n-lte-route.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    st = os.fstat(lock)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o077:
        raise RuntimeError('Untrusted LTE route lock')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = Path('/run') / ('g965n-lte-' + args.invocation + '.json')
    stopping = False

    def stop(_number, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    route = current = None
    try:
        while not stopping:
            state = dict(row.split('=', 1) for row in command(
                'systemctl', 'show', LAB_UNIT, '-p', 'ActiveState', '-p', 'InvocationID').splitlines())
            if state.get('ActiveState') != 'active' or state.get('InvocationID') != args.invocation:
                break
            lease = read_lease(path, time.monotonic())
            if lease != current:
                if route:
                    old, route = route, None
                    old.close()
                current = lease
                if lease:
                    route = Route(lease)
                    route.install()
            if route:
                route.sync_dns()
            time.sleep(.5)
    finally:
        if route:
            route.close()
        os.close(lock)


if __name__ == '__main__':
    main()

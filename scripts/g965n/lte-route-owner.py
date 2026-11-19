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
import tempfile

DEVICE = 'rmnet0'
METRIC = 20000
PROTOCOL = '186'
LABEL = DEVICE + ':g965n'
BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
LAB_UNIT = 'g965n-ril-lab-test.service'


def command(*argv):
    return subprocess.check_output(argv, text=True, timeout=3)


def ip_json(*argv):
    return json.loads(command('ip', '-4', '-j', *argv))


def defaults():
    return ip_json('-N', 'route', 'show', 'default')


def read_private(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'rb') as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o077:
            raise RuntimeError('Unsafe LTE state file')
        raw = stream.read(4097)
    if len(raw) > 4096:
        raise RuntimeError('Oversized LTE state file')
    return json.loads(raw)


def read_lease(path, now):
    record = read_private(path)
    if record is None:
        return None
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


def write_receipt(path, record):
    if path.exists() or path.is_symlink():
        raise RuntimeError('Unrecovered route receipt already exists')
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(record, stream)
            stream.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def link_addresses():
    return json.loads(command('ip', '-j', 'address', 'show', 'dev', DEVICE))


def resolver_values(kind):
    _, sep, settings = command('resolvectl', kind, DEVICE).partition(':')
    if not sep:
        raise RuntimeError('Unexpected per-link resolver status')
    return settings.split()


def owned_default(address):
    return ('default', 'dev', DEVICE, 'src', address, 'metric', str(METRIC), 'proto', PROTOCOL)


def recover_route(path):
    record = read_private(path)
    if record is None:
        return
    if record['boot'] != BOOT_ID.read_text().strip():
        raise RuntimeError('Route receipt belongs to a different boot')
    address = str(ipaddress.IPv4Address(record['address']))
    original_mtu, modem_mtu = record['original_mtu'], record['modem_mtu']
    servers = [str(ipaddress.IPv4Address(value)) for value in record['servers']]
    links = [row for row in ip_json('link', 'show') if row['ifname'] == DEVICE]
    if not links or links[0]['ifindex'] != record['ifindex']:
        path.unlink()
        return  # Original netdev and its per-link configuration are gone.
    link, = links
    settings = link_addresses()[0]['addr_info']
    ours = [row for row in settings if row.get('label') == LABEL and row.get('local') == address
            and row.get('prefixlen') == 32]
    routes = [row for row in defaults() if row['dev'] == DEVICE]
    owned = [row for row in routes if row.get('metric') == METRIC
             and str(row.get('protocol')) == PROTOCOL and row.get('prefsrc') == address]
    dns, domains = resolver_values('dns'), resolver_values('domain')
    if (len(settings) != len(ours) or len(routes) != len(owned)
            or link['mtu'] not in (original_mtu, modem_mtu)
            or (dns and dns != servers) or domains not in ([], ['~.'])):
        raise RuntimeError('Modem interface settings changed ownership; preserve them')
    cleanup = []
    if dns or domains:
        cleanup.append(('resolvectl', 'revert', DEVICE))
    if owned:
        cleanup.append(('ip', '-4', 'route', 'del', *owned_default(address)))
    if ours:
        cleanup.append(('ip', 'address', 'del', address + '/32', 'dev', DEVICE))
    if 'UP' in link['flags'] or link['mtu'] != original_mtu:
        cleanup.append(('ip', 'link', 'set', 'dev', DEVICE, 'mtu', str(original_mtu), 'down'))
    failed = False
    for args in cleanup:
        try:
            command(*args)
        except subprocess.SubprocessError:
            failed = True
    print(json.dumps({'lte_route_removed': record['generation'], 'cleanup_ok': not failed}), flush=True)
    if failed:
        raise RuntimeError('Incomplete LTE route cleanup')
    path.unlink()


class Route:
    def __init__(self, lease, receipt):
        self.generation, address, self.servers, self.mtu = lease
        self.address = address + '/32'
        self.modem_default = owned_default(address)
        self.receipt = receipt
        self.original, = ip_json('link', 'show', 'dev', DEVICE)
        links = link_addresses()
        if (self.original['link_type'] != 'ppp' or 'UP' in self.original['flags']
                or len(links) != 1 or links[0]['addr_info']
                or any(route['dev'] == DEVICE for route in defaults())):
            raise RuntimeError('Expected an idle unmanaged modem interface')
        if resolver_values('dns') or resolver_values('domain'):
            raise RuntimeError('Preserve existing per-link resolver settings')
        self.dns_selected = False

    def install(self):
        write_receipt(self.receipt, {'generation': self.generation, 'address': self.address.split('/')[0],
                      'boot': BOOT_ID.read_text().strip(), 'ifindex': self.original['ifindex'],
                      'original_mtu': self.original['mtu'], 'modem_mtu': self.mtu,
                      'servers': self.servers})
        command('ip', 'link', 'set', 'dev', DEVICE, 'mtu', str(self.mtu), 'up')
        command('ip', 'address', 'add', self.address, 'dev', DEVICE, 'label', LABEL)
        command('ip', '-4', 'route', 'add', *self.modem_default)
        print(json.dumps({'lte_route_active': self.generation}), flush=True)

    def sync_dns(self):
        link, = ip_json('link', 'show', 'dev', DEVICE)
        if link['ifindex'] != self.original['ifindex'] or 'UP' not in link['flags']:
            raise RuntimeError('Modem interface changed')
        rows = defaults()
        if not any(row['dev'] == DEVICE and row.get('metric') == METRIC
                   and str(row.get('protocol')) == PROTOCOL for row in rows):
            raise RuntimeError('Modem default route disappeared')
        preferred = min(rows, key=lambda row: row.get('metric', 0))['dev']
        want_dns = preferred == DEVICE
        if want_dns == self.dns_selected:
            return
        if want_dns:
            command('resolvectl', 'dns', DEVICE, *self.servers)
            command('resolvectl', 'domain', DEVICE, '~.')
            command('resolvectl', 'default-route', DEVICE, 'yes')
        else:
            command('resolvectl', 'revert', DEVICE)
        self.dns_selected = want_dns
        print(json.dumps({'lte_default_dns': want_dns}), flush=True)

    def close(self):
        recover_route(self.receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cleanup', action='store_true', help='Recover owned state after systemd stops the worker')
    parser.add_argument('--invocation', required=True)
    parser.add_argument('--confirm-guarded-g965n-route', action='store_true', required=True)
    args = parser.parse_args()
    if (os.geteuid() != 0 or not re.fullmatch(r'[a-f0-9]{32}', args.invocation)
            or b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0')
            or (not args.cleanup and not Path('/sys/module/g965n_modem').is_dir())):
        raise SystemExit('Expected guarded G965N modem and exact RIL invocation')
    os.umask(0o077)
    lock = os.open('/run/lock/g965n-lte-route.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    st = os.fstat(lock)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_nlink != 1 or st.st_mode & 0o077:
        raise RuntimeError('Untrusted LTE route lock')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = Path('/run') / ('g965n-lte-' + args.invocation + '.json')
    receipt = Path('/run') / ('g965n-lte-route-' + args.invocation + '.json')
    if args.cleanup:
        recover_route(receipt)
        os.close(lock)
        return
    if receipt.exists() or receipt.is_symlink():
        raise RuntimeError('Run route cleanup before restarting the worker')
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
                    route = Route(lease, receipt)
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

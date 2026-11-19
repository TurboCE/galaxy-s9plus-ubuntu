#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded temporary routes for source/device-bound modem DNS and TLS.

Preserve the main default route. Raw evidence stays private.
"""
import argparse
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import signal
from pathlib import Path
import socket
import ssl
import struct
import subprocess


def dns_address(packet, ident, hostname, qtype=1):
    address_length = {1: 4, 28: 16}.get(qtype)
    if address_length is None or len(packet) < 12:
        raise ValueError('Unsupported or short DNS reply')
    rid, flags, questions, answers, _, _ = struct.unpack_from('!HHHHHH', packet)
    if rid != ident or not flags & 0x8000 or flags & 0x7a0f or questions != 1 or answers > 64:
        raise ValueError('Unqualified DNS reply')

    def name(at):
        labels = []
        end = None
        length = 1
        for _ in range(128):
            if at >= len(packet):
                raise ValueError('Truncated DNS name')
            size = packet[at]
            if not size:
                return tuple(labels), end if end is not None else at + 1
            if size & 0xc0 == 0xc0:
                if at + 1 >= len(packet):
                    raise ValueError('Truncated DNS pointer')
                target = (size & 0x3f) << 8 | packet[at + 1]
                if not 12 <= target < at:
                    raise ValueError('Invalid DNS compression pointer')
                if end is None:
                    end = at + 2
                at = target
                continue
            length += size + 1
            if size > 63 or at + 1 + size > len(packet) or length > 255:
                raise ValueError('Bad DNS label or name length')
            labels.append(packet[at + 1:at + 1 + size].lower())
            at += size + 1
        raise ValueError('DNS label bound exceeded')

    question, at = name(12)
    expected = tuple(label.lower().encode('ascii') for label in hostname.rstrip('.').split('.'))
    if question != expected or packet[at:at + 4] != struct.pack('!HH', qtype, 1):
        raise ValueError('Unexpected DNS question')
    at += 4
    addresses = {}
    aliases = {}
    for _ in range(answers):
        owner, at = name(at)
        kind, record_class, _, length = struct.unpack_from('!HHIH', packet, at)
        at += 10
        if at + length > len(packet):
            raise ValueError('Truncated DNS record')
        if record_class == 1 and kind == qtype and length == address_length:
            addresses.setdefault(owner, packet[at:at + length])
        if record_class == 1 and kind == 5:
            target, end = name(at)
            if end != at + length or aliases.setdefault(owner, target) != target:
                raise ValueError('Invalid DNS alias')
        at += length
    visited = set()
    owner = question
    while owner in aliases and owner not in visited:
        visited.add(owner)
        owner = aliases[owner]
    if owner in visited or owner not in addresses:
        raise ValueError('No matching DNS address answer')
    return str(ipaddress.ip_address(addresses[owner]))


def candidate_from(events, expected_generation=None):
    candidate=None;state=None;cleanup=False
    generation = 0
    for event in events:
        if 'pdp_generation' in event:
            next_generation = event['pdp_generation']
            if type(next_generation) is not int or next_generation != generation + 1:
                raise ValueError('Invalid PDP generation sequence')
            if generation and not cleanup:
                raise ValueError('Prior PDP generation was not invalidated')
            generation = next_generation
            candidate, state, cleanup = None, None, False
        if 'pdp_candidate' in event:candidate=event['pdp_candidate']
        if 'pdp_state' in event:state=event['pdp_state']
        if 'pdp_cleanup' in event:cleanup=True
    if generation != (expected_generation or 0):
        raise ValueError('Unexpected PDP generation')
    if not candidate or state!='candidate-ip' or cleanup:raise ValueError('No live qualified PDP candidate')
    if candidate['cid']!=1 or type(candidate['cid']) is not int:raise ValueError('Expected CID1')
    ip=ipaddress.IPv4Address(candidate['ipv4'])
    servers=[str(ipaddress.IPv4Address(x)) for x in candidate['dns4']]
    if ip.is_unspecified or ip.is_multicast or ip.is_loopback or ip.is_link_local or not 1<=len(servers)<=2:
        raise ValueError('Unqualified modem addresses')
    for server in servers:
        value=ipaddress.IPv4Address(server)
        if value.is_unspecified or value.is_multicast or value.is_loopback or value.is_link_local or int(value)==0xffffffff:raise ValueError('Unqualified DNS server')
    if type(candidate['mtu']) is not int or not 576<=candidate['mtu']<=1500:raise ValueError('Unqualified MTU')
    return candidate


POLICY_TABLE = '9650'
POLICY_PRIORITY = '19650'


def bound_socket(interface, address, kind):
    source = ipaddress.ip_address(address)
    if source.is_unspecified or source.is_multicast:
        raise ValueError('Expected a unicast probe source address')
    if source.version == 6:
        if source.ipv4_mapped is not None or source.scope_id is not None:
            raise ValueError('Expected an IPv6 source without an embedded interface or IPv4 address')
        family = socket.AF_INET6
        scope = socket.if_nametoindex(interface) if source.is_link_local else 0
        endpoint = (str(source), 0, 0, scope)
    else:
        family = socket.AF_INET
        endpoint = (str(source), 0)
    probe = socket.socket(family, kind)
    try:
        if family == socket.AF_INET6:
            probe.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode() + b'\0')
        probe.bind(endpoint)
        probe.settimeout(5)
    except BaseException:
        probe.close()
        raise
    return probe


def network_trial(config, policy_route=False):
    name='rmnet0';address=str(ipaddress.IPv4Address(config['ipv4']));servers=config['dns4']
    def output(command):return subprocess.check_output(command,text=True,timeout=5)
    def run(command):subprocess.run(command,check=True,capture_output=True,text=True,timeout=5)
    link=json.loads(output(['ip','-j','link','show','dev',name]))[0]
    if 'UP' in link['flags'] or link['link_type']!='ppp':raise ValueError('Expected unused PPP-type rmnet0')
    if json.loads(output(['ip','-j','address','show','dev',name]))[0]['addr_info']:
        raise ValueError('Preserve existing modem addresses')
    before=json.loads(output(['ip','-j','route','show']))
    policy_rule = ['ip', '-4', 'rule']
    policy_default = ['default', 'dev', name, 'src', address, 'table', POLICY_TABLE]
    policy_selector = ['priority', POLICY_PRIORITY, 'from', address+'/32', 'lookup', POLICY_TABLE]
    def policy_objects():
        rules = json.loads(output(['ip', '-4', '-j', '-N', 'rule', 'show']))
        routes = json.loads(output(['ip', '-4', '-j', '-N', 'route', 'show', 'table', 'all']))
        return ([rule for rule in rules if str(rule.get('priority')) == POLICY_PRIORITY or
                 str(rule.get('table')) == POLICY_TABLE],
                [route for route in routes if str(route.get('table')) == POLICY_TABLE])
    if policy_route and any(policy_objects()):
        raise ValueError('Reserved modem test rule priority or route table is in use')
    default_routes = [route for route in before if route.get('dst') == 'default']
    added=[];up=False;assigned=False
    rule_added = table_default_added = False
    result={'internet_verified':False,'dns_over_modem':False,'route_interface_verified':False,
            'source_and_device_bound':True,'default_route_changed':False,'gateway_invented':False,
            'policy_route_test':policy_route}
    def host_route(target):
        if policy_route:
            return
        dst=str(ipaddress.IPv4Network(target+'/32'))
        for route in before:
            old=route.get('dst','default')
            if old!='default' and ipaddress.ip_network(old)==ipaddress.ip_network(dst):
                raise ValueError('Preserve existing exact host route')
        if target not in added:
            run(['ip','route','add',dst,'dev',name,'src',address]);added.append(target)
    def counters():
        base=Path('/sys/class/net')/name/'statistics'
        return {n:int((base/n).read_text()) for n in ('rx_packets','tx_packets','rx_bytes','tx_bytes','rx_errors','tx_errors')}
    first=counters()
    try:
        run(['ip','link','set','dev',name,'mtu',str(config['mtu']),'up']);up=True
        # /32 is a local point-to-point address assignment, not a claimed
        # network mask supplied by the modem (which may supply no prefix).
        run(['ip','address','add',address+'/32','dev',name]);assigned=True
        if policy_route:
            run(['ip', '-4', 'route', 'add', *policy_default])
            table_default_added = True
            run([*policy_rule, 'add', *policy_selector])
            rule_added = True
        host='connectivitycheck.gstatic.com';ident=int.from_bytes(os.urandom(2),'big')
        query=struct.pack('!HHHHHH',ident,0x100,1,0,0,0)+b''.join(bytes([len(x)])+x.encode() for x in host.split('.'))+b'\0'+struct.pack('!HH',1,1)
        target=None
        for server in servers:
            try:
                host_route(server)
                route=json.loads(output(['ip','-j','route','get',server,'from',address]))[0]
                if route['dev']!=name:raise ValueError('Incorrect test route')
                result['route_interface_verified']=True
                with bound_socket(name,address,socket.SOCK_DGRAM) as s:
                    s.sendto(query,(server,53));packet,peer=s.recvfrom(4096)
                if peer!=(server,53):raise ValueError('Unexpected DNS peer')
                target=dns_address(packet,ident,host);result['dns_over_modem']=True;break
            except (OSError,ValueError,IndexError,struct.error):continue
        if not target:raise ValueError('No DNS answer through modem')
        host_route(target)
        if policy_route:
            ordinary = json.loads(output(['ip', '-4', '-j', 'route', 'get', target]))[0]
            selected = json.loads(output(['ip', '-4', '-j', '-N', 'route', 'get', target,
                                          'from', address]))[0]
            if (ordinary['dev'] == name or selected['dev'] != name or
                    str(selected.get('table')) != POLICY_TABLE):
                raise ValueError('Policy route did not isolate the modem source')
            result['policy_route_isolated'] = True
        with bound_socket(name,address,socket.SOCK_STREAM) as plain:
            plain.connect((target,443))
            with ssl.create_default_context().wrap_socket(plain,server_hostname=host) as tls:
                tls.sendall(('GET /generate_204 HTTP/1.1\r\nHost: '+host+'\r\nConnection: close\r\n\r\n').encode())
                header=b''
                while b'\r\n' not in header and len(header)<4096:
                    chunk=tls.recv(4096-len(header))
                    if not chunk:break
                    header+=chunk
                result['https_status']=int(header.split(b'\r\n',1)[0].split()[1])
                result['internet_verified']=result['https_status']==204
    except Exception as error:result['failure_type']=type(error).__name__
    finally:
        if rule_added:
            subprocess.run([*policy_rule, 'del', *policy_selector], capture_output=True, timeout=5)
        if table_default_added:
            subprocess.run(['ip', '-4', 'route', 'del', *policy_default], capture_output=True, timeout=5)
        for target in reversed(added):
            subprocess.run(['ip','route','del',target+'/32','dev',name,'src',address],capture_output=True)
        if assigned:subprocess.run(['ip','address','del',address+'/32','dev',name],capture_output=True)
        if up:
            subprocess.run(['ip','link','set','dev',name,'down'],capture_output=True)
            subprocess.run(['ip','link','set','dev',name,'mtu',str(link['mtu'])],capture_output=True)
        last=counters();result['counter_delta']={k:last[k]-v for k,v in first.items()}
        result['temporary_state_cleanup_requested']=True
        current_link=json.loads(output(['ip','-j','link','show','dev',name]))[0]
        current_addr=json.loads(output(['ip','-j','address','show','dev',name]))[0]['addr_info']
        current_routes=json.loads(output(['ip','-j','route','show']))
        remaining=any(str(x.get('dst','')).split('/')[0] in added and x.get('dev')==name for x in current_routes)
        result['default_route_changed'] = default_routes != [
            route for route in current_routes if route.get('dst') == 'default']
        policy_remaining = policy_route and any(policy_objects())
        result['temporary_state_restored'] = (
            not remaining and not policy_remaining and not result['default_route_changed']
            and not current_addr and 'UP' not in current_link['flags']
            and current_link['mtu'] == link['mtu'])
    return result


def wifi_fallback_trial(config, usb_peer, require_live):
    """Exercise ordinary app traffic through an owned standby IPv4 default."""
    modem, wifi = 'rmnet0', 'wlp1s0'
    host = 'connectivitycheck.gstatic.com'
    address = config['ipv4']
    env = {**os.environ, 'LC_ALL': 'C'}

    def run(*cmd, timeout=6, check=True):
        return subprocess.run(cmd, capture_output=True, text=True, env=env,
                              timeout=timeout, check=check)

    def query(*cmd):
        return json.loads(run(*cmd).stdout)

    def defaults():
        return query('ip', '-4', '-j', 'route', 'show', 'default')

    def active_wifi():
        for line in run('nmcli', '-t', '-f', 'UUID,DEVICE', 'connection', 'show',
                        '--active').stdout.splitlines():
            uuid, _, device = line.partition(':')
            if device == wifi and re.fullmatch(r'[a-fA-F0-9-]{36}', uuid):
                return uuid
        return None

    def app_request(device):
        require_live()
        result = run('runuser', '-u', 'nobody', '--', 'curl', '-q', '-4', '--noproxy', '*',
                     '--max-time', '10', '-fsS', '-o', '/dev/null',
                     '-w', '%{http_code} %{local_ip} %{remote_ip}',
                     f'https://{host}/generate_204', timeout=12)
        code, local, remote = result.stdout.split()
        route, = query('ip', '-4', '-j', 'route', 'get', remote)
        if code != '204' or route['dev'] != device or (local == address) != (device == modem):
            raise RuntimeError('Unbound application used an unexpected route')

    def traffic():
        base = Path('/sys/class/net') / modem / 'statistics'
        return {key: int((base / key).read_text()) for key in
                ('rx_packets', 'tx_packets', 'rx_errors', 'tx_errors')}

    proved = {'wifi_preferred': False, 'unbound_lte_https204': False,
              'uncached_dns_over_lte': False, 'wifi_recovered': False,
              'temporary_state_restored': False}
    wifi_uuid = active_wifi()
    incumbent, = defaults()
    if incumbent['dev'] != wifi or incumbent.get('metric', 0) >= 20000 or not wifi_uuid:
        raise ValueError('Expected one existing preferred Wi-Fi default')
    peer_route, = query('ip', '-4', '-j', 'route', 'get', str(ipaddress.IPv4Address(usb_peer)))
    if peer_route['dev'] != 'usb0' or peer_route.get('gateway'):
        raise ValueError('Expected a direct USB management route')
    link, = query('ip', '-j', 'link', 'show', 'dev', modem)
    def addresses():
        return query('ip', '-j', 'address', 'show', 'dev', modem)[0]['addr_info']
    if 'UP' in link['flags'] or link['link_type'] != 'ppp' or addresses():
        raise ValueError('Expected an unused modem data interface')

    route = ('default', 'dev', modem, 'src', address, 'metric', '20000')
    up_wifi = ('nmcli', '-w', '25', 'connection', 'up', 'uuid', wifi_uuid, 'ifname', wifi)
    timer_unit = 'g965n-fallback-wifi-restore'
    for suffix in ('.timer', '.service'):
        state = run('systemctl', 'show', timer_unit + suffix, '-p', 'LoadState',
                    '--value', check=False).stdout.strip()
        if state != 'not-found':
            raise RuntimeError('Wi-Fi restoration unit name is already in use')
    link_changed = address_added = route_added = dns_changed = wifi_changed = timer_added = False
    try:
        require_live()
        run('ip', 'link', 'set', 'dev', modem, 'mtu', str(config['mtu']), 'up')
        link_changed = True
        run('ip', 'address', 'add', address + '/32', 'dev', modem)
        address_added = True
        run('ip', '-4', 'route', 'add', *route)
        route_added = True
        app_request(wifi)
        proved['wifi_preferred'] = True
        run('systemd-run', '--collect', '--unit=' + timer_unit, '--on-active=70s',
            '--timer-property=AccuracySec=1s', '/usr/bin/' + up_wifi[0], *up_wifi[1:])
        timer_added = True
        wifi_changed = True
        run('nmcli', '-w', '8', 'device', 'disconnect', wifi, timeout=10)
        selected, = defaults()
        if selected['dev'] != modem:
            raise RuntimeError('LTE did not replace the unavailable Wi-Fi default')
        require_live()
        dns_changed = True
        run('resolvectl', 'dns', modem, *config['dns4'])
        run('resolvectl', 'domain', modem, '~.')
        run('resolvectl', 'default-route', modem, 'yes')
        before = traffic()
        dns = run('resolvectl', '-4', '--cache=no', 'query', host, timeout=8).stdout
        if f'-- link: {modem}' not in dns:
            raise RuntimeError('Uncached system lookup did not use modem DNS')
        proved['uncached_dns_over_lte'] = True
        app_request(modem)
        proved['unbound_lte_https204'] = True
        proved['counter_delta'] = {key: value - before[key] for key, value in traffic().items()}
    except (subprocess.SubprocessError, OSError, RuntimeError, ValueError) as error:
        proved['failure_type'] = type(error).__name__
    finally:
        def restore(*cmd, timeout=6):
            try:
                return run(*cmd, timeout=timeout, check=False).returncode == 0
            except (subprocess.SubprocessError, OSError):
                return False

        dns_restored = True
        if dns_changed:
            dns_restored = restore('resolvectl', 'revert', modem)
        if route_added:
            restore('ip', '-4', 'route', 'del', *route)
        if address_added:
            restore('ip', 'address', 'del', address + '/32', 'dev', modem)
        if link_changed:
            restore('ip', 'link', 'set', 'dev', modem, 'mtu', str(link['mtu']), 'down')
        if wifi_changed:
            restore(*up_wifi, timeout=30)
        restored, = query('ip', '-j', 'link', 'show', 'dev', modem)
        proved['wifi_recovered'] = active_wifi() == wifi_uuid and defaults() == [incumbent]
        if timer_added and proved['wifi_recovered']:
            restore('systemctl', 'stop', timer_unit + '.timer')
        proved['temporary_state_restored'] = (
            dns_restored and proved['wifi_recovered'] and not addresses() and 'UP' not in restored['flags']
            and restored['mtu'] == link['mtu'])
    return proved


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',choices=['SM-G965N'],required=True)
    p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--receipt-sha256',required=True);p.add_argument('--backup-sha256',required=True)
    p.add_argument('--guard-sha256',required=True)
    p.add_argument('--trial',type=Path,required=True)
    p.add_argument('--confirm-backup-verified',action='store_true')
    p.add_argument('--consent-pdp-network-test',action='store_true')
    p.add_argument('--policy-route', action='store_true',
                   help='Verify a temporary source rule and separate modem routing table')
    p.add_argument('--pdp-generation', type=int)
    p.add_argument('--wifi-fallback-usb-peer', type=ipaddress.IPv4Address,
                   help='Explicit Wi-Fi interruption trial; requires a direct USB management peer')
    args=p.parse_args();os.umask(0o077)
    if args.pdp_generation is not None and not 1 <= args.pdp_generation <= 999999999:
        p.error('Expected a positive PDP generation with at most nine digits')
    if args.wifi_fallback_usb_peer and args.policy_route:
        p.error('Choose a policy probe or the bounded ordinary-app fallback trial')
    if os.geteuid()!=0 or not args.confirm_backup_verified or not args.consent_pdp_network_test:
        raise ValueError('Root, verified backup and network-test consent required')
    guard_path=args.profile/'package/p2p-control-trial.py';data=guard_path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=args.guard_sha256:raise ValueError('Unexpected model/backup guard')
    spec=importlib.util.spec_from_file_location('data_trial_guard',guard_path)
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    guard.validate(guard.trusted_json(args.profile/'startup.json',args.receipt_sha256),guard.trusted_json(args.profile/'backup.json',args.backup_sha256),require_off=False)
    if not Path('/sys/module/g965n_modem').exists():raise ValueError('Expected reviewed loaded modem')
    unit='g965n-ril-lab-test.service'
    invocation=(args.trial/'invocation-private.txt').read_text().strip()
    def live_candidate():
        if invocation!=subprocess.check_output(['systemctl','show',unit,'-p','InvocationID','--value'],text=True).strip():raise ValueError('Changed RIL invocation')
        if subprocess.check_output(['systemctl','show',unit,'-p','ActiveState','--value'],text=True).strip()!='active':raise ValueError('RIL must remain active')
        events=[]
        for line in subprocess.check_output(['journalctl','-b','_SYSTEMD_INVOCATION_ID='+invocation,'-o','cat','--no-pager'],text=True).splitlines():
            try:events.append(json.loads(line))
            except ValueError:pass
        return candidate_from(events, args.pdp_generation)
    def interrupted(number,frame):raise InterruptedError('Bounded network trial interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    config = live_candidate()
    if args.wifi_fallback_usb_peer:
        def require_live():
            if live_candidate() != config:
                raise RuntimeError('Modem address configuration changed')
        result = wifi_fallback_trial(config, args.wifi_fallback_usb_peer, require_live)
    else:
        result=network_trial(config, policy_route=args.policy_route)
    if args.pdp_generation is not None:
        result['pdp_generation'] = args.pdp_generation
    out=args.trial/'network-test-private.json'
    with out.open('x') as f:json.dump(result,f,indent=2)
    out.chmod(0o600);print(json.dumps(result))


if __name__=='__main__':main()

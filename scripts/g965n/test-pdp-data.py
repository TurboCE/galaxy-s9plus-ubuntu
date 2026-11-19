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
import signal
from pathlib import Path
import socket
import ssl
import struct
import subprocess


def dns_a(packet,ident):
    if len(packet)<12:raise ValueError('Short DNS reply')
    rid,flags,questions,answers,_,_=struct.unpack_from('!HHHHHH',packet)
    if rid!=ident or not flags&0x8000 or flags&0x020f or questions!=1 or answers>64:
        raise ValueError('Unqualified DNS reply')
    def skip(at):
        for _ in range(128):
            size=packet[at];at+=1
            if not size:return at
            if size&0xc0==0xc0:
                if at>=len(packet):raise ValueError('Truncated DNS pointer')
                return at+1
            if size>63 or at+size>len(packet):raise ValueError('Bad DNS label')
            at+=size
        raise ValueError('DNS label bound exceeded')
    at=skip(12)+4
    for _ in range(answers):
        at=skip(at);kind,cls,ttl,length=struct.unpack_from('!HHIH',packet,at);at+=10
        if at+length>len(packet):raise ValueError('Truncated DNS record')
        if kind==1 and cls==1 and length==4:return str(ipaddress.IPv4Address(packet[at:at+4]))
        at+=length
    raise ValueError('No DNS A answer')


def candidate_from(events):
    candidate=None;state=None;cleanup=False
    for event in events:
        if 'pdp_candidate' in event:candidate=event['pdp_candidate']
        if 'pdp_state' in event:state=event['pdp_state']
        if 'pdp_cleanup' in event:cleanup=True
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
    def bound(kind):
        s=socket.socket(socket.AF_INET,kind)
        s.setsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,name.encode()+b'\0')
        s.bind((address,0));s.settimeout(5);return s
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
                with bound(socket.SOCK_DGRAM) as s:
                    s.sendto(query,(server,53));packet,peer=s.recvfrom(4096)
                if peer!=(server,53):raise ValueError('Unexpected DNS peer')
                target=dns_a(packet,ident);result['dns_over_modem']=True;break
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
        with bound(socket.SOCK_STREAM) as plain:
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
    args=p.parse_args();os.umask(0o077)
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
    if invocation!=subprocess.check_output(['systemctl','show',unit,'-p','InvocationID','--value'],text=True).strip():raise ValueError('Changed RIL invocation')
    if subprocess.check_output(['systemctl','show',unit,'-p','ActiveState','--value'],text=True).strip()!='active':raise ValueError('RIL must remain active')
    events=[]
    for line in subprocess.check_output(['journalctl','-b','_SYSTEMD_INVOCATION_ID='+invocation,'-o','cat','--no-pager'],text=True).splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    def interrupted(number,frame):raise InterruptedError('Bounded network trial interrupted')
    signal.signal(signal.SIGTERM,interrupted)
    result=network_trial(candidate_from(events), policy_route=args.policy_route)
    out=args.trial/'network-test-private.json'
    with out.open('x') as f:json.dump(result,f,indent=2)
    out.chmod(0o600);print(json.dumps(result))


if __name__=='__main__':main()

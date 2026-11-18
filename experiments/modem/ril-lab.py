#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded G965N IPC/RFS bring-up using private NV copies and an explicit APN.

Not a complete telephony service. No calls/SMS/PIN operations or arbitrary RFS
file access. Network layouts follow the documented stock S9 protocol research
in ztOS modem/README.md at8bfb09011757f06c68a055fbfd95ea07d5e4fbe1; original code.
"""
import argparse
from contextlib import ExitStack
import fcntl
import importlib.util
import json
import ipaddress
import math
import signal
import os
from pathlib import Path
import re
import select
import struct
import time
from collections import deque

spec = importlib.util.spec_from_file_location('rfs_copy', Path(__file__).with_name('rfs-copy.py'))
rfs_copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(rfs_copy)


# Protocol facts only: LineageOS/android_hardware_samsung_samsung-ipc,
# 6d244414f7c66b0d0f93ef4b34f5276023408016, include/gprs.h and gen.h.
# GPL-2.0-or-later reference; this is an independent GPL-2.0-only implementation.
# IMPORTANT: that reference describes 103-byte activation / 27-byte IPv4,
# not an established SM-G965N 105-byte / 257-byte layout. Never transmit this
# reference profile on the S9 without a separately reviewed target mapping.
REFERENCE_PROTOCOL = 'lineage-ipc-6d244414-reference-only'


def reference_define_pdp(apn, cid=1):
    if not re.fullmatch(r'[A-Za-z0-9.-]{1,100}', apn) or type(cid) is not int or not 1 <= cid <= 3:
        raise ValueError('Invalid bounded reference APN/CID')
    return bytes((1, cid, 2)) + apn.encode('ascii').ljust(124, b'\0')


def reference_activate_pdp(cid=1, enable=True):
    if type(cid) is not int or not 1 <= cid <= 3 or type(enable) is not bool:
        raise ValueError('Invalid reference CID/enable')
    # No authentication credentials: all reserved/auth fields are zero.
    return bytes((int(enable), cid)) + bytes(101)


def reference_ip_config(body, cid=1):
    if len(body) != 27 or body[0] != cid or body[2] != 0:
        raise ValueError('Unqualified/failed reference IP configuration')
    values = [str(ipaddress.IPv4Address(body[offset:offset+4])) for offset in (3, 7, 11, 15, 19)]
    address = ipaddress.IPv4Address(values[0])
    if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local or int(address) == 0xffffffff:
        raise ValueError('Unusable PDP IPv4 address')
    dns = []
    for value in values[1:3]:
        address = ipaddress.IPv4Address(value)
        if not (address.is_unspecified or address.is_multicast or address.is_loopback or address.is_link_local or int(address) == 0xffffffff):
            dns.append(value)
    return {'ipv4': values[0], 'dns': dns, 'gateway': values[3], 'netmask': values[4],
            'field_flag': body[1]}


class ReferencePDPPlan:
    """Pure bounded protocol plan: no I/O, routes, or claim of internet access.

    Emitted tuples are legacy test vectors only. The live loop never uses this
    profile; S9 has a separate source-qualified candidate and explicit opt-in.
    """
    def __init__(self, apn, now, timeout=30):
        self.definition = reference_define_pdp(apn)
        if not 1 <= timeout <= 60:
            raise ValueError('Bounded PDP deadline required')
        self.deadline = now + timeout
        self.state = 'await-registration'
        self.pending = None
        self.enabled = False
        self.configuration = None

    def tick(self, now):
        if now >= self.deadline and self.state not in ('failed', 'candidate-ip'):
            self.state = 'failed'; self.pending = None
        return self.state

    def registered(self, now):
        if self.tick(now) != 'await-registration':
            return None
        self.state = 'define-pending'; self.pending = 0x0D01
        return (0x0D01, self.definition)

    def ack(self, body, now):
        if self.tick(now) == 'failed':
            return None
        if len(body) != 5:
            raise ValueError('Reference generic response must be five bytes')
        group, index, kind, result = struct.unpack('<BBBH', body)
        if group << 8 | index != self.pending or kind != 3:
            return None
        if result != 0x8000:
            self.state = 'failed'; self.pending = None
            return None
        if self.pending == 0x0D01:
            self.state = 'activate-pending'; self.pending = 0x0D04
            return (0x0D04, reference_activate_pdp())
        self.pending = None; self.state = 'await-ip-and-status'
        self._candidate()
        return None

    def event(self, command, body, now):
        if self.tick(now) not in ('activate-pending', 'await-ip-and-status', 'candidate-ip'):
            return
        if command == 0x0D10:
            if len(body) != 4 or body[0] != 1:
                raise ValueError('Unqualified reference PDP status')
            if body[1] != 1 or body[2] != 0:
                self.state = 'failed'; self.pending = None
                return
            self.enabled = True
        elif command == 0x0D09:
            self.configuration = reference_ip_config(body)
        self._candidate()

    def _candidate(self):
        if self.state == 'await-ip-and-status' and self.enabled and self.configuration:
            # Candidate address only; never equivalent to DNS/HTTPS validation.
            self.state = 'candidate-ip'


# S9-specific facts independently established from the owner's stock
# libsec-ril.so IpcProtocol41::{IpcTxSetPdpContext,IpcTxDefinePdpContext,
# IpcRxIpConfiguration,IpcRxGprsCallStatus} and DataLink::Dump symbols.
# Only wire-layout facts are represented below. No binary, disassembly, source
# implementation, credentials or handset identifiers are redistributed.
S9_PROTOCOL = 'g965n-ipc41-source-candidate'


def s9_define_pdp(apn, cid=1):
    if not isinstance(apn, str):
        raise ValueError('S9 APN must be an explicit string')
    reference_define_pdp(apn, cid)  # shared conservative APN/CID validation
    # IPv4 wire type2; internal DataProtocol enums are not wire values.
    return bytes((1, cid, 2)) + apn.encode('ascii').ljust(101, b'\0') + bytes(23)


def s9_activate_pdp(cid=1, enable=True):
    reference_activate_pdp(cid, enable)  # shared CID/bool validation only
    # state,cid; LE32 presence flags; username32,password32,reserved32;
    # auth,reserved,reason. This lab supports no-credential/default-reason only.
    return bytes((int(enable), cid)) + bytes(103)


def _usable_address(value):
    return not (value.is_unspecified or value.is_multicast or value.is_loopback or
                value.is_link_local or (value.version == 4 and int(value) == 0xffffffff))


def s9_ip_config(body, cid=1):
    if type(cid) is not int or not 1 <= cid <= 3 or len(body) not in (157, 257) or body[0] != cid:
        raise ValueError('Unsupported S9 IP layout/CID')
    flags = struct.unpack_from('<H', body, 1)[0]
    result = {'cid': cid, 'flags': flags, 'unknown_flags': flags & ~0x6059,
              'ipv4': None, 'dns4': [], 'gateway': None, 'prefix4': None,
              'ipv6': None, 'dns6': [], 'mtu': None,
              'gateway_source': 'not-provided', 'prefix_source': 'not-provided',
              'raw_hex': body.hex()}
    def address(offset, version):
        size = 4 if version == 4 else 16
        return ipaddress.ip_address(bytes(body[offset:offset+size]))
    if flags & 1:
        value = address(3, 4)
        if not _usable_address(value):
            raise ValueError('Unusable S9 IPv4 address')
        result['ipv4'] = str(value)
        result['dns4'] = [str(value) for value in (address(7, 4), address(11, 4)) if _usable_address(value)]
    if flags & 8:
        value = address(15, 4)
        if not _usable_address(value):
            raise ValueError('Unusable supplied S9 gateway')
        result.update(gateway=str(value), gateway_source='modem-supplied')
    if flags & 16:
        mask = int(address(19, 4)); inverted = (~mask) & 0xffffffff
        if inverted & (inverted + 1):
            raise ValueError('Noncontiguous supplied S9 netmask')
        result.update(prefix4=mask.bit_count(), prefix_source='modem-supplied')
    if flags & 64:
        value = address(35, 6)
        if not _usable_address(value):
            raise ValueError('Unusable S9 IPv6 address')
        result['ipv6'] = str(value)
        result['dns6'] = [str(value) for value in (address(99, 6), address(115, 6)) if _usable_address(value)]
    if flags & 8192:
        mtu = struct.unpack_from('<I', body, 152)[0]
        minimum = 1280 if result['ipv6'] else 576
        if not minimum <= mtu <= 65535:
            raise ValueError('S9 MTU outside supported range')
        result['mtu'] = mtu
    # Do not invent defaults for absent gateway/mask or interpret unknown bits.
    # Byte156 is PCO-related when bit14 is set; structure/units are unqualified.
    result['pco_raw'] = body[156] if flags & 16384 else None
    v4_offsets = [23 + 4*j for j in range(3)]
    v6_offsets = [51 + 16*j for j in range(3)]
    if len(body) == 257:
        v4_offsets += [145 + 4*j for j in range(3, 8)]
        v6_offsets += [129 + 16*j for j in range(3, 8)]
    result['pcscf4_raw'] = [str(address(offset, 4)) for offset in v4_offsets]
    result['pcscf6_raw'] = [str(address(offset, 6)) for offset in v6_offsets]
    if not result['ipv4'] and not result['ipv6']:
        raise ValueError('S9 IP message does not supply a usable address')
    return result


def s9_pdp_status(body, cid=1):
    if type(cid) is not int or not 1 <= cid <= 3 or len(body) != 9 or body[0] != cid or body[3] not in (0, 1):
        raise ValueError('Unsupported S9 status layout/CID/boolean')
    return {'cid': cid, 'raw_state': body[1], 'active': body[1] == 1,
            'raw_end_reason': body[2], 'aux_flag': bool(body[3]),
            'additional_status': body[4], 'throttle_timer_raw': struct.unpack_from('<I', body, 5)[0],
            'raw_hex': body.hex()}


class S9PDPPlan:
    """One activation, pure transitions; candidate IP is never internet proof."""
    def __init__(self, apn, cid, now, timeout=30):
        self.definition = s9_define_pdp(apn, cid)
        if type(timeout) is not int or not 1 <= timeout <= 60:
            raise ValueError('Bounded S9 PDP deadline required')
        self._time(now)
        self.cid = cid; self.deadline = now + timeout
        self.state = 'await-registration'; self.reason = None
        self.pending = None; self.activation_issued = False; self.cleanup_issued = False
        self.configuration = None; self.status = None; self.report_emitted = False

    @staticmethod
    def _time(now):
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise ValueError('Finite monotonic PDP time required')

    def fail(self, reason):
        self.state = 'failed'; self.reason = reason; self.pending = None

    def tick(self, now):
        self._time(now)
        if now >= self.deadline and self.state not in ('failed', 'finished'):
            self.fail('deadline')
        return self.state

    def registered(self, confirmed, now):
        if self.tick(now) != 'await-registration' or confirmed is not True:
            return None
        self.state = 'define-pending'; self.pending = 0x0D01
        return (0x0D01, self.definition)

    def ack(self, body, now):
        if self.tick(now) in ('failed', 'finished'):
            return None
        if len(body) != 5:
            self.fail('malformed-ack'); return None
        group, index, kind, result = struct.unpack('<BBBH', body)
        if (group << 8 | index) != self.pending or kind != 3:
            return None
        if result != 0x8000:
            self.fail('negative-ack'); return None
        if self.pending == 0x0D01 and not self.activation_issued:
            self.activation_issued = True; self.pending = 0x0D04
            self.state = 'activate-pending'
            return (0x0D04, s9_activate_pdp(self.cid))
        self.pending = None; self.state = 'await-ip-and-status'
        self._candidate()
        return None

    def event(self, command, body, now, kind=3):
        if self.tick(now) not in ('activate-pending', 'await-ip-and-status', 'candidate-ip'):
            return
        if body and body[0] != self.cid:
            return  # another context cannot satisfy or destroy this plan
        if kind != 3:
            self.fail('unexpected-event-kind'); return
        try:
            if command == 0x0D09:
                self.configuration = s9_ip_config(body, self.cid)
                if not self.configuration['ipv4']:
                    self.fail('ipv4-not-provided'); return
            elif command == 0x0D10:
                self.status = s9_pdp_status(body, self.cid)
                if not self.status['active']:
                    self.fail('context-not-active'); return
        except ValueError:
            self.fail('malformed-event'); return
        self._candidate()

    def _candidate(self):
        if self.state == 'await-ip-and-status' and self.status and self.status['active'] and self.configuration:
            self.state = 'candidate-ip'

    def candidate_report(self):
        if self.state != 'candidate-ip' or self.report_emitted:
            return None
        self.report_emitted = True
        config = self.configuration
        return {'pdp_candidate': {'cid': self.cid, 'ipv4': config['ipv4'],
                                  'dns4': list(config['dns4']), 'gateway': config['gateway'],
                                  'prefix4': config['prefix4'], 'mtu': config['mtu']},
                'internet_verified': False, 'private_journal_only': True}

    def cp_reset(self):
        self.activation_issued = False  # never send stale cleanup to a new CP
        self.fail('cp-reset')

    def cleanup(self):
        if not self.activation_issued or self.cleanup_issued:
            return None
        self.cleanup_issued = True
        return (0x0D04, s9_activate_pdp(self.cid, enable=False))


def cereg_registration(body):
    # Match the complete numeric status. Prefix matching 10 as 1 could activate
    # data while not actually registered. Query responses carry n,status.
    matches = list(re.finditer(rb'\+CEREG:\s*[0-5],\s*(\d{1,2})[ \t]*(?=[,\r\n])', body))
    return int(matches[-1][1]) in (1, 5) if matches else None


def validate_s9_opt_in(args):
    selected = bool(args.activate_pdp_s9)
    if selected != bool(args.confirm_reviewed_s9_pdp_layout):
        raise ValueError('S9 PDP requires both explicit opt-in and reviewed-layout confirmation')
    if selected:
        if not args.configure_radio or args.pdp_cid != 1:
            raise ValueError('Initial S9 live lab requires explicit radio configuration and CID1')
        s9_define_pdp(args.apn, args.pdp_cid)
    return selected


def require_qualified_s9_pdp():
    raise RuntimeError('Legacy profile blocked for S9; use the separately reviewed S9 source candidate')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, choices=range(10, 181), default=90)
    parser.add_argument('--apn')
    parser.add_argument('--configure-radio', action='store_true')
    parser.add_argument('--runtime-helper', type=Path, required=True)
    parser.add_argument('--expected-receipt-sha256', required=True)
    parser.add_argument('--activate-pdp-s9', action='store_true')
    parser.add_argument('--confirm-reviewed-s9-pdp-layout', action='store_true')
    parser.add_argument('--pdp-cid', type=int, choices=(1,), default=1)
    parser.add_argument('--pdp-seconds', type=int, choices=range(10,61), default=30)
    args = parser.parse_args()
    if args.configure_radio and (not args.apn or not re.fullmatch(r'[A-Za-z0-9.-]{1,100}', args.apn)):
        raise SystemExit('Explicit valid APN required for radio configuration')
    pdp_opt_in = validate_s9_opt_in(args)
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected star2lte')
    os.umask(0o077)
    with ExitStack() as stack:
        helper = args.runtime_helper
        if helper.is_symlink() or not helper.is_file():
            raise RuntimeError('Missing reviewed runtime helper')
        runtime_spec = importlib.util.spec_from_file_location('ril_child_runtime', helper)
        runtime = importlib.util.module_from_spec(runtime_spec)
        runtime_spec.loader.exec_module(runtime)
        stack.enter_context(runtime.shared_runtime_lock())
        runtime.validate_launch_state(args.expected_receipt_sha256)
        lock_fd = os.open('/run/lock/g965n-modem-probe.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        lock = stack.enter_context(open(lock_fd, 'rb', closefd=True))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        nv = rfs_copy.WorkingNV('/var/lib/g965n-vendor-runtime/efs')
        stack.callback(nv.close)
        fds = []
        for name in ('umts_ipc0', 'umts_rfs0', 'umts_router'):
            fd = os.open('/dev/' + name, os.O_RDWR | os.O_NONBLOCK)
            stack.callback(os.close, fd); fds.append(fd)
        ipc, rfs, at = fds
        buffers = {ipc: bytearray(), rfs: bytearray()}
        sequence = 0
        configured = False
        saw_boot = False
        sim_ready = False
        acknowledged = set()
        radio_asked = False
        radio_at = 0
        radio_retried = False
        registered = False
        registration_at = None
        pdp_plan = None
        pdp_previous_state = None
        stop_requested = False
        at_queue = deque()
        at_active = None
        at_buffer = bytearray()
        at_ready = False
        at_failed = False
        boot_at = None
        next_at_ping = 0
        started = time.monotonic()
        next_at = started + 5

        def send(command, body=b'', kind=3):
            nonlocal sequence
            sequence = sequence % 254 + 1
            message = struct.pack('<HBBBBB', len(body) + 7, sequence, 255, command >> 8, command & 255, kind) + body
            if os.write(ipc, message) != len(message):
                raise RuntimeError('Short IPC write')
            print(json.dumps({'sent_command': hex(command), 'bytes': len(body)}), flush=True)

        def cleanup_pdp():
            if pdp_plan is None:
                return
            request = pdp_plan.cleanup()
            if request:
                try:
                    send(*request)
                    print(json.dumps({'pdp_cleanup': 'deactivation-requested-not-confirmed'}), flush=True)
                except (OSError, RuntimeError):
                    print(json.dumps({'pdp_cleanup': 'write-failed-not-retried'}), flush=True)

        stack.callback(cleanup_pdp)
        def stop(signum, frame):
            nonlocal stop_requested
            stop_requested = True
        for number in (signal.SIGTERM, signal.SIGINT):
            previous = signal.signal(number, stop)
            stack.callback(signal.signal, number, previous)

        while not stop_requested and time.monotonic() - started < args.seconds:
            now = time.monotonic()
            if pdp_opt_in and pdp_plan is None and registered and registration_at is not None and now-registration_at <= 15 and sim_ready and radio_asked and at_ready and not at_failed:
                pdp_plan = S9PDPPlan(args.apn, args.pdp_cid, now, timeout=args.pdp_seconds)
                request = pdp_plan.registered(True, now)
                if request:
                    send(*request)
            if pdp_plan is not None:
                if not registered:
                    pdp_plan.fail('registration-lost')
                pdp_plan.tick(now)
                if pdp_plan.state == 'failed':
                    cleanup_pdp()
                if pdp_previous_state != pdp_plan.state:
                    pdp_previous_state = pdp_plan.state
                    print(json.dumps({'pdp_state': pdp_plan.state, 'reason': pdp_plan.reason,
                                      'internet_verified': False}), flush=True)
                report = pdp_plan.candidate_report()
                if report is not None:
                    print(json.dumps(report), flush=True)
            if args.configure_radio and not configured and saw_boot and sim_ready:
                attach = bytearray(194)
                attach[:3] = bytes((1, 1, 2))
                attach[3:3 + len(args.apn)] = args.apn.encode('ascii')
                attach[192] = 2
                send(0x0D14, attach)  # LTE attach profile
                send(0x080A, b'\x0b')  # LTE/WCDMA/GSM
                send(0x0808, b'\x01')  # stock combined circuit/packet service
                configured = True
            if at_ready and not at_failed and time.monotonic() >= next_at:
                if 'AT+CEREG?' not in at_queue and (not at_active or at_active[0] != 'AT+CEREG?'):
                    at_queue.append('AT+CEREG?')
                next_at += 10
            if at_ready and not at_failed and configured and acknowledged == {0x0D14, 0x080A, 0x0808} and not radio_asked:
                at_queue.appendleft('AT+CFUN=1')
                radio_asked = True
                radio_at = time.monotonic()
            if not pdp_opt_in and not at_failed and radio_asked and not registered and not radio_retried and time.monotonic() - radio_at > 25:
                at_queue.extend(['AT+CFUN=4', 'AT+CFUN=1'])
                radio_retried = True
            if not at_ready and not at_failed and boot_at and time.monotonic() - boot_at >= 3 and time.monotonic() >= next_at_ping and not at_active:
                at_queue.appendleft('AT')  # harmless readiness check, never retry a state change blindly
                next_at_ping = time.monotonic() + 3
            if not at_failed and not at_active and at_queue:
                command = at_queue.popleft()
                packet = (command + '\r').encode('ascii')
                if os.write(at, packet) != len(packet):
                    raise RuntimeError('Short AT command write')
                at_active = (command, time.monotonic())
                at_buffer.clear()
                print(json.dumps({'at_command': command}), flush=True)
            if at_active and time.monotonic() - at_active[1] > (2 if at_active[0] == 'AT' else 20):
                print(json.dumps({'at_timeout': at_active[0], 'rfs_kept_running': True}), flush=True)
                if at_active[0] != 'AT' or (boot_at and time.monotonic() - boot_at > 30):
                    at_failed = True
                    at_queue.clear()
                at_active = None
                at_buffer.clear()
            for fd in select.select(fds, [], [], .1)[0]:
                chunk = os.read(fd, 65536)
                if not chunk:
                    raise RuntimeError('Modem channel closed')
                if fd == at:
                    print(json.dumps({'at_status': chunk.decode('ascii', 'replace')}), flush=True)
                    at_buffer.extend(chunk)
                    if len(at_buffer) > 65536:
                        raise RuntimeError('AT response exceeds bounded buffer')
                    reported = cereg_registration(at_buffer)
                    if reported is not None:
                        registered = reported
                        registration_at = time.monotonic()
                    echoed = at_active and (at_active[0] + '\r').encode('ascii') in at_buffer
                    if echoed and (b'\r\nOK\r\n' in at_buffer or b'ERROR' in at_buffer):
                        if at_active[0] == 'AT' and b'\r\nOK\r\n' in at_buffer:
                            at_ready = True
                        at_active = None
                        at_buffer.clear()
                    continue
                buffer = buffers[fd]; buffer.extend(chunk)
                header = 6 if fd == rfs else 7
                while len(buffer) >= header:
                    length = struct.unpack_from('<I' if fd == rfs else '<H', buffer)[0]
                    if length < header or length > 16 * 1024 * 1024 + 14:
                        raise ValueError('Invalid modem frame size')
                    if len(buffer) < length:
                        break
                    message = bytes(buffer[:length]); del buffer[:length]
                    if fd == rfs:
                        reply = nv.handle(message)
                        if os.write(rfs, reply) != len(reply):
                            raise RuntimeError('Short RFS reply')
                        print(json.dumps({'rfs_command': message[4], 'bytes': length, 'private_copy_only': True}), flush=True)
                    else:
                        _, _, _, group, command, kind = struct.unpack_from('<HBBBBB', message)
                        code = group << 8 | command
                        event = {'command': hex(code), 'kind': kind, 'bytes': length - 7}
                        if code == 0x0101:
                            if pdp_plan is not None:
                                pdp_plan.cp_reset()
                            saw_boot = True
                            configured = False
                            acknowledged.clear()
                            radio_asked = False
                            radio_retried = False
                            registered = False
                            registration_at = None
                            at_ready = False
                            at_failed = False
                            at_active = None
                            at_queue.clear()
                            at_buffer.clear()
                            sim_ready = False
                            boot_at = time.monotonic()
                        if code == 0x8001 and length >= 12:
                            if pdp_plan is not None:
                                request = pdp_plan.ack(message[7:], time.monotonic())
                                if request:
                                    send(*request)
                            event['request_command'] = hex(message[7] << 8 | message[8])
                            event['result_code'] = struct.unpack_from('<H', message, 10)[0]
                            request = message[7] << 8 | message[8]
                            if request in (0x0D14, 0x080A, 0x0808) and event['result_code'] == 0x8000:
                                acknowledged.add(request)
                        elif code in (0x0D09, 0x0D10) and pdp_plan is not None:
                            pdp_plan.event(code, message[7:], time.monotonic(), kind=kind)
                        elif code == 0x0501 and length > 7:
                            event['sim_status_code'] = message[7]
                            sim_ready = message[7] in (0, 130)
                        elif code == 0x0805 and length >= 10:
                            event['access_technology_code'] = message[7]
                            event['domain_code'] = message[8]
                            event['registration_code'] = message[9]
                        print(json.dumps(event), flush=True)


if __name__ == '__main__':
    main()

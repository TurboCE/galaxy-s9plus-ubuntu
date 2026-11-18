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
import os
from pathlib import Path
import re
import select
import struct
import time
from collections import deque

spec = importlib.util.spec_from_file_location('rfs_copy', Path(__file__).with_name('rfs-copy.py'))
rfs_copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(rfs_copy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, choices=range(10, 181), default=90)
    parser.add_argument('--apn')
    parser.add_argument('--configure-radio', action='store_true')
    args = parser.parse_args()
    if args.configure_radio and (not args.apn or not re.fullmatch(r'[A-Za-z0-9.-]{1,100}', args.apn)):
        raise SystemExit('Explicit valid APN required for radio configuration')
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected star2lte')
    os.umask(0o077)
    with ExitStack() as stack:
        lock = stack.enter_context(open('/run/lock/g965n-modem-probe.lock', 'w'))
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

        while time.monotonic() - started < args.seconds:
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
            if not at_failed and radio_asked and not registered and not radio_retried and time.monotonic() - radio_at > 25:
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
                    for match in re.finditer(rb'\+CEREG:\s*\d+,([0-5])', at_buffer):
                        registered = int(match[1]) in (1, 5)
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
                            saw_boot = True
                            sim_ready = False
                            boot_at = time.monotonic()
                        if code == 0x8001 and length >= 12:
                            event['request_command'] = hex(message[7] << 8 | message[8])
                            event['result_code'] = struct.unpack_from('<H', message, 10)[0]
                            request = message[7] << 8 | message[8]
                            if request in (0x0D14, 0x080A, 0x0808) and event['result_code'] == 0x8000:
                                acknowledged.add(request)
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

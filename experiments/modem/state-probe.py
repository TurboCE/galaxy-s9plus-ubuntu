#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded modem state probe: open startup channels and send status GETs only.

Samsung IPC framing/status definitions reference LineageOS libsamsung-ipc
commit6d244414f7c66b0d0f93ef4b34f5276023408016 (GPL-2.0-or-later).
This original diagnostic does not send SMS, place calls, set PINs, modify NV,
or serve remote filesystem requests. It never prints identity/location payloads.
"""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import select
import struct
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, choices=range(5, 61), default=20)
    args = parser.parse_args()
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected star2lte')
    with ExitStack() as stack:
        lock = stack.enter_context(open('/run/lock/g965n-modem-probe.lock', 'w'))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        descriptors = []
        for name in ('umts_ipc0', 'umts_rfs0'):
            fd = os.open('/dev/' + name, os.O_RDWR | os.O_NONBLOCK)
            stack.callback(os.close, fd)
            descriptors.append(fd)
        ipc, rfs = descriptors
        sequence = 0
        buffer = bytearray()
        started = time.monotonic()
        next_query = started + 2
        while time.monotonic() - started < args.seconds:
            if time.monotonic() >= next_query:
                # State-only commands. Do not request IMSI/IMEI/subscriber/cell data.
                for command in (0x0107, 0x0501):
                    sequence = sequence % 254 + 1
                    packet = struct.pack('<HBBBBB', 7, sequence, 0xff, command >> 8, command & 255, 2)
                    try:
                        count = os.write(ipc, packet)
                        print(json.dumps({'query': hex(command), 'accepted_bytes': count}), flush=True)
                    except OSError as error:
                        print(json.dumps({'query': hex(command), 'errno': error.errno}), flush=True)
                next_query += 6
            for fd in select.select(descriptors, [], [], .2)[0]:
                chunk = os.read(fd, 65536)
                if not chunk:
                    raise RuntimeError('Modem channel closed')
                if fd == rfs:
                    print(json.dumps({'rfs_request_bytes': len(chunk), 'served': False}), flush=True)
                    continue
                buffer.extend(chunk)
                while len(buffer) >= 7:
                    size, mseq, aseq, group, command, kind = struct.unpack_from('<HBBBBB', buffer)
                    if size < 7:
                        raise RuntimeError('Invalid Samsung IPC frame length')
                    if len(buffer) < size:
                        break
                    body = buffer[7:size]
                    del buffer[:size]
                    code = group << 8 | command
                    result = {'command': hex(code), 'kind': kind, 'payload_bytes': len(body)}
                    if code == 0x0501 and body:
                        result['sim_status_code'] = body[0]
                    elif code == 0x0107 and body:
                        result['phone_state_code'] = body[0]
                    elif code == 0x0805 and len(body) >= 3:
                        result.update({'access_technology_code': body[0], 'domain_code': body[1],
                                       'registration_code': body[2]})
                    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

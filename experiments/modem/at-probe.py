#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Query a booted modem through its AT router; optional radio enable only.

No SMS/call/PIN/identity commands. Standard CFUN/CPIN/CEREG/CGATT status queries
are used; CFUN=1 is sent only with the explicit --enable-radio option.
This is not a complete RIL or remote-filesystem server.
"""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import select
import time
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-radio', action='store_true')
    parser.add_argument('--apn', help='Explicit temporary IPv4 context1 APN (no credentials)')
    parser.add_argument('--attach-data', action='store_true')
    args = parser.parse_args()
    if args.apn and not re.fullmatch(r'[A-Za-z0-9.-]{1,100}', args.apn):
        raise SystemExit('Invalid APN')
    if args.attach_data and not args.apn:
        raise SystemExit('Data attach requires an explicit APN')
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected star2lte')
    with ExitStack() as stack:
        lock = stack.enter_context(open('/run/lock/g965n-modem-probe.lock', 'w'))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fds = []
        for name in ('umts_ipc0', 'umts_rfs0', 'umts_router'):
            fd = os.open('/dev/' + name, os.O_RDWR | os.O_NONBLOCK)
            stack.callback(os.close, fd)
            fds.append(fd)
        commands = ['AT', 'AT+CFUN?', 'AT+CPIN?']
        if args.apn:
            commands += ['AT+CGDCONT=1,"IP","' + args.apn + '"']
        if args.enable_radio:
            commands += ['AT+CFUN=1']
        if args.attach_data:
            commands += ['AT+CGATT=1']
        commands += ['AT+CREG?', 'AT+CGREG?', 'AT+CEREG?', 'AT+CGATT?', 'AT+COPS?', 'AT+CESQ', 'AT+CEER', 'AT+CGDCONT?']
        for command in commands:
            packet = (command + '\r').encode('ascii')
            if os.write(fds[2], packet) != len(packet):
                raise RuntimeError('Short AT write')
            response = bytearray()
            deadline = time.monotonic() + (25 if command in ('AT+CFUN=1', 'AT+CGATT=1') else 3)
            complete = False
            while time.monotonic() < deadline:
                for fd in select.select(fds, [], [], .2)[0]:
                    chunk = os.read(fd, 65536)
                    if fd == fds[2]:
                        response.extend(chunk)
                if b'\r\nOK\r\n' in response or b'ERROR' in response:
                    complete = True
                    break
            # These queries return no subscriber identity or cell identifiers.
            # Keep raw output private anyway: unsolicited modem output may vary.
            print(json.dumps({'command': command, 'response': response.decode('ascii', 'replace')}), flush=True)
            if not complete:
                raise TimeoutError('AT command timed out; do not misassign a late reply to the next command')


if __name__ == '__main__':
    main()

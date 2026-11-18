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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-radio', action='store_true')
    args = parser.parse_args()
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
        if args.enable_radio:
            commands += ['AT+CFUN=1']
        commands += ['AT+CEREG?', 'AT+CGATT?', 'AT+COPS?']
        for command in commands:
            packet = (command + '\r').encode('ascii')
            if os.write(fds[2], packet) != len(packet):
                raise RuntimeError('Short AT write')
            response = bytearray()
            deadline = time.monotonic() + (10 if command == 'AT+CFUN=1' else 3)
            while time.monotonic() < deadline:
                for fd in select.select(fds, [], [], .2)[0]:
                    chunk = os.read(fd, 65536)
                    if fd == fds[2]:
                        response.extend(chunk)
                if b'\r\nOK\r\n' in response or b'ERROR' in response:
                    break
            # These queries return no subscriber identity or cell identifiers.
            # Keep raw output private anyway: unsolicited modem output may vary.
            print(json.dumps({'command': command, 'response': response.decode('ascii', 'replace')}), flush=True)


if __name__ == '__main__':
    main()

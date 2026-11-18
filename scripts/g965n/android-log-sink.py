#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture vendor-program Android log datagrams inside the private test runtime.

Diagnostic only; not an Android logd implementation. Never publish its output.
"""
import argparse
import os
from pathlib import Path
import signal
import socket


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run as root')
    directory = Path('/run/g965n-vendor-runtime/root/dev/socket')
    if not os.path.ismount(directory.parents[1]):
        raise SystemExit('Private vendor runtime is not mounted')
    os.umask(0o077)
    directory.mkdir(mode=0o755, exist_ok=True)
    directory.chmod(0o755)  # cbd drops to Android radio; parent runtime stays private
    path = directory / 'logdw'
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    with args.output.open('x') as output, socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as server:
        server.bind(str(path))
        os.chown(path, 0, 1001)
        path.chmod(0o660)
        try:
            while True:
                output.write(repr(server.recv(65536)) + '\n')
                output.flush()
        finally:
            path.unlink(missing_ok=True)


if __name__ == '__main__':
    main()

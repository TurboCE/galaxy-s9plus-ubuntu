#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only GNSS tap to a private PTY and loopback-only GPSD for xgps."""
import os
from pathlib import Path
import pty
import pwd
import select
import signal
import socket
import subprocess
import termios
import tty

ROOT = Path('/run/g965n-xgps')

def main():
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, exist_ok=True)
    endpoint = ROOT / 'nmea.sock'
    endpoint.unlink(missing_ok=True)
    master, slave = pty.openpty()
    tty.setraw(slave)
    user = pwd.getpwnam('gpsd')
    os.fchown(slave, user.pw_uid, user.pw_gid)
    os.fchmod(slave, 0o600)
    stream = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    stream.bind(str(endpoint))
    stream.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    process = subprocess.Popen(['/usr/sbin/gpsd', '-N', '-n', '-b', '-S', '2948', os.ttyname(slave)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Receiver controls never reach the real HAL: discard PTY output. GPSD -b
    # additionally disables probing/configuration of this virtual device.
    packets = 0
    try:
        while process.poll() is None:
            ready, _, _ = select.select([stream, master], [], [], 1)
            if master in ready:
                os.read(master, 8192)
            if stream in ready:
                import struct
                data, ancillary, flags, _ = stream.recvmsg(8192, socket.CMSG_SPACE(12))
                trusted = any(level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS
                              and struct.unpack('3i', value[:12])[1] == 0
                              for level, kind, value in ancillary)
                if trusted and not flags & socket.MSG_TRUNC:
                    os.write(master, data)
                    packets += 1
                    if packets == 1 or packets % 120 == 0:
                        print(f"Forwarded {packets} GNSS chunks", flush=True)
        raise RuntimeError('GPSD exited')
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
        stream.close(); os.close(master); os.close(slave)
        endpoint.unlink(missing_ok=True)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    main()

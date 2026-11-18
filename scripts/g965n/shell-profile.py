#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture the real GNOME compositor while the owner exercises the UI.

Raw Sysprof captures can contain private application information. Keep them out
of Git. This does not disable desktop access restrictions or change UI/settings.
"""
import argparse
import os
from pathlib import Path
import signal
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, choices=range(5, 61), default=25)
    args = parser.parse_args()
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected native star2lte')
    from gi.repository import Gio, GLib
    os.umask(0o077)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    fds = Gio.UnixFDList.new()
    index = fds.append(fd)
    service = ('org.gnome.Shell', '/org/gnome/Sysprof3/Profiler', 'org.gnome.Sysprof3.Profiler')
    started = False

    def interrupted(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        bus.call_with_unix_fd_list_sync(*service, 'Start',
            GLib.Variant('(a{sv}h)', ({}, index)), None, Gio.DBusCallFlags.NONE, 5000, fds, None)
        started = True
        print('PROFILE_STARTED: exercise the application overview now.', flush=True)
        time.sleep(args.seconds)
    finally:
        try:
            if started:
                bus.call_sync(*service, 'Stop', None, None, Gio.DBusCallFlags.NONE, 5000, None)
        finally:
            os.close(fd)
    print('PROFILE_COMPLETE: private capture bytes=' + str(args.output.stat().st_size))


if __name__ == '__main__':
    main()

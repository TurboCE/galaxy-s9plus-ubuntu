#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Relay the standard magnetic heading to the selected local desktop user."""
import math
import os
import select
import socket
import struct
import time

from gi.repository import Gio, GLib

SOCKET = '/run/g965n-compass/heading.sock'
NAME = 'net.hadess.SensorProxy'
PATH = '/net/hadess/SensorProxy/Compass'
INTERFACE = NAME + '.Compass'
PROPERTIES = 'org.freedesktop.DBus.Properties'


def serve(peer):
    _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != os.stat(SOCKET).st_uid:
        raise PermissionError('Wrong local compass socket owner')
    peer.settimeout(2)
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM)

    def call(interface, method, arguments=None):
        return bus.call_sync(NAME, PATH, interface, method, arguments, None,
                             Gio.DBusCallFlags.NONE, 1500, None)

    def prop(key):
        return call(PROPERTIES, 'Get', GLib.Variant('(ss)', (INTERFACE, key))).unpack()[0]

    claimed = False
    ready_at = 0
    try:
        while not select.select([peer], [], [], .7)[0]:
            heading = None
            try:
                available = prop('HasCompass')
                if available and not claimed:
                    call(INTERFACE, 'ClaimCompass')
                    claimed = True
                    ready_at = time.monotonic() + 1.4
                if available and time.monotonic() >= ready_at:
                    value = prop('CompassHeading')
                    if math.isfinite(value) and 0 <= value < 360:
                        heading = value
            except GLib.Error:
                # The standard service can disappear and reappear with its IIO device.
                # ClaimCompass is idempotent for the same D-Bus caller.
                claimed = False
            peer.sendall(b'\n' if heading is None else f'{heading:.3f}\n'.encode('ascii'))
    except (BrokenPipeError, ConnectionResetError, TimeoutError):
        pass
    finally:
        if claimed:
            try:
                call(INTERFACE, 'ReleaseCompass')
            except GLib.Error:
                pass


if __name__ == '__main__':
    with socket.socket(fileno=os.dup(0)) as connection:
        serve(connection)

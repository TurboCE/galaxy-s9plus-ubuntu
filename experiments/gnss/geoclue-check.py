#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check desktop location delivery without reading or printing coordinates."""
import argparse
import json
import time
import gi
from gi.repository import Gio, GLib


def check(seconds):
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    service = 'org.freedesktop.GeoClue2'
    manager = '/org/freedesktop/GeoClue2/Manager'
    iface = service + '.Client'

    def call(path, interface, method, arguments=None):
        return bus.call_sync(service, path, interface, method, arguments, None,
                             Gio.DBusCallFlags.NONE, 10000, None)

    def get(path, interface, key):
        return call(path, 'org.freedesktop.DBus.Properties', 'Get',
                    GLib.Variant('(ss)', (interface, key))).unpack()[0]

    client = call(manager, service + '.Manager', 'GetClient').unpack()[0]
    try:
        for key, value in [('DesktopId', GLib.Variant('s', 'g965n-gps-test')),
                           ('RequestedAccuracyLevel', GLib.Variant('u', 8))]:
            call(client, 'org.freedesktop.DBus.Properties', 'Set',
                 GLib.Variant('(ssv)', (iface, key, value)))
        call(client, iface, 'Start')
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            location = get(client, iface, 'Location')
            if location != '/':
                timestamp = get(location, service + '.Location', 'Timestamp')
                age = time.time() - timestamp[0]
                accuracy = get(location, service + '.Location', 'Accuracy')
                if 0 <= age < 30 and 0 <= accuracy < 100:
                    print(json.dumps({'fresh_desktop_location': True,
                                      'accuracy_meters': accuracy,
                                      'age_seconds': round(age, 1)}))
                    return True
            time.sleep(1)
        print(json.dumps({'fresh_desktop_location': False}))
        return False
    finally:
        try:
            call(client, iface, 'Stop')
        finally:
            call(manager, service + '.Manager', 'DeleteClient', GLib.Variant('(o)', (client,)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=90)
    args = parser.parse_args()
    if not 15 <= args.seconds <= 180:
        parser.error('--seconds must be 15–180')
    raise SystemExit(0 if check(args.seconds) else 2)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Set the phone desktop to 2x scaling using Mutter's supported display API.

Run as the logged-in desktop user. Refuses multiple/external displays. Most
desktop windows fit 720 logical pixels; larger application minima still exist.
"""
from gi.repository import Gio, GLib


def main():
    proxy = Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION, 0, None, 'org.gnome.Mutter.DisplayConfig',
        '/org/gnome/Mutter/DisplayConfig', 'org.gnome.Mutter.DisplayConfig', None)
    serial, monitors, logical, properties = proxy.call_sync('GetCurrentState', None, 0, 5000, None).unpack()
    if len(monitors) != 1 or len(logical) != 1 or not monitors[0][2].get('is-builtin'):
        raise SystemExit('Expected just the phone built-in display')
    spec, modes, _ = monitors[0]
    mode = next(m for m in modes if m[-1].get('is-current'))
    if tuple(mode[1:3]) != (1440, 2960) or 2.0 not in mode[5]:
        raise SystemExit('Unexpected panel mode or unsupported 2x scale')
    request = GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})', (
        serial, 2, [(0, 0, 2.0, 0, True, [(spec[0], mode[0], {})])], {}))
    proxy.call_sync('ApplyMonitorsConfig', request, 0, 5000, None)
    settings = Gio.Settings.new('org.gnome.mutter')
    settings.set_boolean('auto-maximize', True)
    settings.set_boolean('center-new-windows', True)
    Gio.Settings.sync()
    print('Requested persistent 2x scale: 720x1480 logical pixels.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Temporary white GTK test surface; no settings, sensors or brightness writes.

Run as the ordinary Wayland desktop user. Automatically closes after75seconds.
The optional private state reports focus/fullscreen, not optical luminance.
"""
import argparse
import json
import os
from pathlib import Path
import time

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Use the normal desktop user')
    window = Gtk.Window(title='G965N temporary white backlight test')
    window.connect('destroy', Gtk.main_quit)
    area = Gtk.DrawingArea()
    def draw(_area, context):
        context.set_source_rgb(1, 1, 1)
        context.paint()
        return False
    area.connect('draw', draw)
    window.add(area)
    window.fullscreen()
    window.show_all()
    window.present()
    def record():
        native = window.get_window()
        value = {'monotonic_s': time.monotonic(), 'active': window.is_active(),
                 'fullscreen': bool(native and native.get_state() & Gdk.WindowState.FULLSCREEN)}
        fd = os.open(args.state, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
        return False
    GLib.timeout_add_seconds(3, record)
    GLib.timeout_add_seconds(75, lambda: (window.destroy(), False)[1])
    Gtk.main()


if __name__ == '__main__':
    main()

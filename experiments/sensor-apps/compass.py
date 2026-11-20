#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Display live magnetic heading from the local desktop compass socket."""
import math
import socket
import threading

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

SOCKET = '/run/g965n-compass/heading.sock'
ARROWS = ('↑', '↖', '←', '↙', '↓', '↘', '→', '↗')
APP = Gtk.Application(application_id='org.g965n.Compass')


def activate(application):
    previous = application.get_active_window()
    if previous:
        previous.present()
        return

    window = Gtk.ApplicationWindow(application=application, title='나침반')
    window.set_default_size(320, 380)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                   margin_top=28, margin_bottom=28, margin_start=22, margin_end=22)
    window.set_child(body)
    title = Gtk.Label(label='나침반')
    title.add_css_class('title-1')
    body.append(title)
    arrow = Gtk.Label()
    body.append(arrow)
    reading = Gtk.Label()
    reading.add_css_class('title-1')
    body.append(reading)
    details = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
    details.add_css_class('dim-label')
    body.append(details)

    stopped = threading.Event()
    window.connect('close-request', lambda *_: stopped.set() or False)

    def show(heading):
        if stopped.is_set():
            return False
        if heading is None:
            arrow.set_markup('<span size="60000">—</span>')
            reading.set_text('센서 연결 대기')
            details.set_text('휴대폰을 평평하게 들면 센서를 다시 확인합니다.')
        else:
            pointer = ARROWS[int((heading + 22.5) // 45) % len(ARROWS)]
            arrow.set_markup(f'<span size="60000">{pointer}</span>')
            reading.set_text(f'{heading:.1f}°')
            details.set_text('자북 기준 · 시험 모드\n방향 및 기울기 보정 진행 중')
        return False

    def watch():
        while not stopped.is_set():
            try:
                with socket.socket(socket.AF_UNIX) as peer:
                    peer.settimeout(4)
                    peer.connect(SOCKET)
                    with peer.makefile('rb') as source:
                        while not stopped.is_set():
                            line = source.readline(32)
                            if not line or not line.endswith(b'\n'):
                                break
                            heading = float(line) if line.strip() else None
                            if heading is not None and not (math.isfinite(heading) and 0 <= heading < 360):
                                heading = None
                            GLib.idle_add(show, heading)
            except (OSError, ValueError):
                pass
            GLib.idle_add(show, None)
            stopped.wait(1)

    show(None)
    window.present()
    threading.Thread(target=watch, daemon=True).start()


APP.connect('activate', activate)
APP.run()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Display only real, coordinate-free measurements from the GNSS test unit."""
import json
from pathlib import Path
import time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk

UNIT = 'g965n-gps-test.service'
SUMMARY = Path('/run/g965n-gps-test/summary.json')


class TestApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.g965n.GPSTest')
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def do_activate(self):
        if self.get_active_window():
            self.get_active_window().present()
            return
        window = Gtk.ApplicationWindow(application=self, title='GPS 수신 시험')
        window.set_default_size(340, 480)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                      margin_start=20, margin_end=20, margin_top=20, margin_bottom=20)
        box.append(Gtk.Label(label='하늘이 보이는 곳에서 5분간 측정합니다.\nUSB 없이 사용할 수 있습니다.', wrap=True))
        self.status = Gtk.Label(wrap=True, xalign=0)
        self.details = Gtk.Label(wrap=True, xalign=0)
        box.append(self.status)
        box.append(self.details)
        start = Gtk.Button(label='5분 측정 시작')
        start.connect('clicked', lambda _: self.command('StartUnit'))
        stop = Gtk.Button(label='측정 중지')
        stop.connect('clicked', lambda _: self.command('StopUnit'))
        box.append(start)
        box.append(stop)
        box.append(Gtk.Label(label='GPS 좌표를 저장하지 않고 수신 통계만 표시합니다.\n직접 수신 시험을 시작하기 전에는 지도 앱을 닫아 주세요.', wrap=True))
        window.set_child(box)
        window.present()
        self.refresh()
        GLib.timeout_add_seconds(1, self.refresh)

    def command(self, method):
        self.status.set_text('요청 중…')
        self.bus.call('org.freedesktop.systemd1', '/org/freedesktop/systemd1',
                      'org.freedesktop.systemd1.Manager', method,
                      GLib.Variant('(ss)', (UNIT, 'fail')), None,
                      Gio.DBusCallFlags.NONE, 5000, None, self.completed)

    def completed(self, bus, result):
        try:
            bus.call_finish(result)
        except GLib.Error:
            self.status.set_text('측정을 시작하지 못했습니다. 서비스 상태를 확인해 주세요.')

    def refresh(self):
        try:
            state = json.loads(SUMMARY.read_text())
            age = time.time() - state['updated_at']
            active = 0 <= age < 45 and not state['final']
            title = 'GPS 위치 확정 확인' if state['fix_observed'] else '아직 GPS 위치가 잡히지 않았습니다.'
            if state.get('source_closed'):
                active = False
                title = 'GPS 수신 서비스 연결이 종료되었습니다.'
            self.status.set_text(title + ('\n측정 중' if active else '\n이전 측정 결과 — 다시 측정할 수 있습니다.'))
            in_view = state['satellites_in_view_max'] if state['sentence_types'].get('GSV') else '미수신'
            self.details.set_text(
                f"측정 시간: {state['elapsed_seconds']}초\n"
                f"정상 수신 문장: {state['valid_sentences']}\n"
                f"가시 위성 보고값(위성군별 최대): {in_view}\n"
                f"사용 위성(최대): {state['satellites_used_max']}\n"
                f"오류 문장: {state['invalid_sentences']}")
        except (OSError, ValueError, KeyError, TypeError):
            self.status.set_text('측정 시작을 눌러 실제 GPS 수신을 확인하세요.')
            self.details.set_text('위치 확정 전까지는 정상 동작으로 판정하지 않습니다.')
        return True


if __name__ == '__main__':
    TestApp().run()

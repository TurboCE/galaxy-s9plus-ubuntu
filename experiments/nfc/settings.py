#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Desktop NFC controls using neard's standard D-Bus interfaces."""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk

SERVICE = 'org.neard'
ADAPTER = 'org.neard.Adapter'
PROPERTIES = 'org.freedesktop.DBus.Properties'


class Settings(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='org.g965n.NFCSettings')
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.adapter = None
        self.busy = False
        self.refreshing = False
        self.pending = False

    def do_activate(self):
        if self.get_active_window():
            self.get_active_window().present()
            return
        window = Gtk.ApplicationWindow(application=self, title='NFC')
        window.set_default_size(340, 420)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                          margin_start=20, margin_end=20, margin_top=20, margin_bottom=20)
        self.status = Gtk.Label(xalign=0, wrap=True)
        content.append(self.status)
        row = Gtk.Box(spacing=12)
        row.append(Gtk.Label(label='NFC 켜기', hexpand=True, xalign=0))
        self.power = Gtk.CheckButton()
        self.power.connect('toggled', self.power_changed)
        row.append(self.power)
        content.append(row)
        self.scan = Gtk.Button(label='태그 검색 시작')
        self.scan.connect('clicked', self.scan_clicked)
        content.append(self.scan)
        self.records = Gtk.Label(label='태그를 휴대폰 뒷면에 대세요.', xalign=0, wrap=True,
                                 selectable=True)
        content.append(self.records)
        window.set_child(content)
        window.present()
        self.refresh()
        GLib.timeout_add_seconds(1, self.refresh)

    def refresh(self):
        if self.busy or self.pending:
            return True
        self.busy = True
        self.bus.call(SERVICE, '/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects',
                      None, None, Gio.DBusCallFlags.NONE, 3000, None, self.refreshed)
        return True

    def refreshed(self, bus, result):
        self.busy = False
        if self.pending:
            return
        try:
            objects = bus.call_finish(result).unpack()[0]
            adapters = [(path, interfaces[ADAPTER]) for path, interfaces in objects.items()
                        if ADAPTER in interfaces]
            if not adapters:
                raise RuntimeError('사용 가능한 NFC 장치가 없습니다.')
            self.adapter, state = adapters[0]
            powered = state.get('Powered', False)
            polling = state.get('Polling', False)
            self.refreshing = True
            self.power.set_active(powered)
            self.refreshing = False
            self.power.set_sensitive(True)
            self.scan.set_sensitive(powered)
            self.scan.set_label('태그 검색 중지' if polling else '태그 검색 시작')
            self.polling = polling
            tags = [interfaces['org.neard.Tag'] for interfaces in objects.values()
                    if 'org.neard.Tag' in interfaces]
            self.status.set_text('NFC 태그를 인식했습니다.' if tags else
                                 '태그를 검색하고 있습니다.' if polling else
                                 'NFC가 켜져 있습니다.' if powered else 'NFC가 꺼져 있습니다.')
            text = []
            for interfaces in objects.values():
                record = interfaces.get('org.neard.Record')
                if record:
                    for key in ('Type', 'Representation', 'URI', 'MIMEType'):
                        value = record.get(key)
                        if isinstance(value, str) and value:
                            text.append(value[:4096])
            self.records.set_text('\n'.join(text) if text else
                                  '태그는 인식됐지만 표시할 NDEF 데이터가 없습니다.' if tags else
                                  '태그를 휴대폰 뒷면에 대세요. 태그에 따라 읽을 수 있는 정보가 다릅니다.')
        except (GLib.Error, RuntimeError) as error:
            self.status.set_text(str(error))
            self.power.set_sensitive(False)
            self.scan.set_sensitive(False)
            self.adapter = None

    def request(self, interface, method, arguments=None):
        if not self.adapter or self.pending:
            return
        self.pending = True
        self.power.set_sensitive(False)
        self.scan.set_sensitive(False)
        self.bus.call(SERVICE, self.adapter, interface, method, arguments, None,
                      Gio.DBusCallFlags.NONE, 8000, None, self.completed)

    def completed(self, bus, result):
        self.pending = False
        try:
            bus.call_finish(result)
        except GLib.Error as error:
            self.status.set_text(error.message)
        self.refresh()

    def power_changed(self, switch):
        if not self.refreshing:
            self.request(PROPERTIES, 'Set',
                         GLib.Variant('(ssv)', (ADAPTER, 'Powered',
                                               GLib.Variant('b', switch.get_active()))))

    def scan_clicked(self, _button):
        if getattr(self, 'polling', False):
            self.request(ADAPTER, 'StopPollLoop')
        else:
            self.request(ADAPTER, 'StartPollLoop', GLib.Variant('(s)', ('Initiator',)))


if __name__ == '__main__':
    Settings().run()

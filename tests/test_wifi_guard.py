# SPDX-License-Identifier: GPL-2.0-only
import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'device/base/usr/local/sbin/s9p-wifi-guard'
loader = importlib.machinery.SourceFileLoader('wifi_guard', str(PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class WifiTests(unittest.TestCase):
    def run_guard(self, state='30 (disconnected)', radio='enabled', automatic='yes'):
        calls = []
        def run(*args):
            calls.append(args)
            if args == ('-t', 'radio', 'wifi'): return radio
            if args[:3] == ('-t', '-f', 'DEVICE,TYPE'): return 'wlan9:wifi\nusb0:ethernet'
            if args[:2] == ('-g', 'GENERAL.STATE'): return state
            if args[:3] == ('-t', '-f', 'UUID,TYPE,TIMESTAMP'): return 'saved:802-11-wireless:100'
            if args[:2] == ('-g', 'connection.autoconnect'): return automatic
            if args[:2] == ('-g', '802-11-wireless.mode'): return 'infrastructure'
            return ''
        guard = module.Guard(run)
        guard.step()
        self.assertFalse(any(c[0] == '--wait' for c in calls))
        guard.step()
        return calls

    def test_dynamic_interface_and_bounded_reconnect(self):
        calls = self.run_guard()
        self.assertIn(('--wait', '20', 'connection', 'up', 'uuid', 'saved', 'ifname', 'wlan9'), calls)

    def test_in_progress_connection_not_interrupted(self):
        calls = self.run_guard(state='40 (connecting)')
        self.assertFalse(any(c[0] == '--wait' for c in calls))

    def test_manual_profiles_and_disabled_radio_respected(self):
        for settings in ({'automatic': 'no'}, {'radio': 'disabled'}):
            with self.subTest(settings=settings):
                calls = self.run_guard(**settings)
                self.assertFalse(any(c[0] == '--wait' for c in calls))

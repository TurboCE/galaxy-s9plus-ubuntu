# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('backlight_restore',ROOT/'scripts/g965n/backlight-restore.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class BacklightRestoreTests(unittest.TestCase):
    def test_wrong_boot_cannot_write_settings_or_hardware(self):
        with patch.object(b,'verify_boot',side_effect=ValueError('wrong BOOT')),patch.object(b,'desktop_settings') as settings:
            with self.assertRaises(ValueError):b.restore({'boot_sha256':'a'*64,'boot_bytes':32},False)
            settings.assert_not_called()

    def test_recovery_keeps_auto_dimming_off_and_manual_restores_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            p=Path(temporary)
            for name,value in [('max_brightness','16'),('actual_brightness','16'),('brightness','1')]:
                p.joinpath(name).write_text(value)
            value={'boot_sha256':'a'*64,'boot_bytes':32,'ambient_enabled':True,'maximum':16}
            with patch.object(b,'verify_boot'),patch.object(b,'BACKLIGHT',p),patch.object(b,'desktop_settings') as settings:
                b.restore(value,True)
                self.assertEqual(settings.call_args_list,[unittest.mock.call('set','org.gnome.settings-daemon.plugins.power','ambient-enabled','false')])
                self.assertEqual(p.joinpath('brightness').read_text(),'16\n')
                settings.reset_mock();b.restore(value,False)
                self.assertEqual(settings.call_args_list[-1].args[-1],'true')
                settings.reset_mock();p.joinpath('actual_brightness').write_text('1')
                with patch.object(b.time,'monotonic',side_effect=[0,7]):
                    with self.assertRaises(RuntimeError):b.restore(value,False)
                self.assertEqual(settings.call_args_list[-1].args[-1],'false')
                p.joinpath('max_brightness').write_text('255');settings.reset_mock()
                with self.assertRaises(ValueError):b.restore(value,True)
                settings.assert_not_called()


    def test_new_range_requires_exact_saved_range_and_waits_for_actual(self):
        with tempfile.TemporaryDirectory() as temporary:
            p=Path(temporary)
            for name,value in [('max_brightness','401'),('actual_brightness','401'),('brightness','5')]:p.joinpath(name).write_text(value)
            state={'boot_sha256':'a'*64,'boot_bytes':32,'ambient_enabled':True,'maximum':401}
            with patch.object(b,'verify_boot'),patch.object(b,'BACKLIGHT',p),patch.object(b,'desktop_settings') as settings:
                b.restore(state,True)
                self.assertEqual(p.joinpath('brightness').read_text(),'401\n')
                state['maximum']=16;settings.reset_mock()
                with self.assertRaises(ValueError):b.restore(state,False)
                settings.assert_not_called()

if __name__=='__main__':unittest.main()

# SPDX-License-Identifier: GPL-2.0-only
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import time
import unittest

SPEC = importlib.util.spec_from_file_location(
    'gnss_supervisor', Path(__file__).resolve().parents[1] / 'experiments/gnss/serve.py')
GNSS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GNSS)


class Supervision(unittest.TestCase):
    def test_receiver_config_only_disables_android_sensor_aiding(self):
        original = b'<glgps xmlns="http://www.glpals.com/"><hal PortName="lhd"/><gll FrqPlan="unchanged"/></glgps>'
        expected = original.replace(b'<hal ', b'<hal SensorsEnable="false" ')
        self.assertEqual(GNSS.receiver_config(original), expected)

    def test_receiver_config_replaces_existing_true_idempotently(self):
        original = b'<glgps xmlns="http://www.glpals.com/"><hal SensorsEnable="true" PortName="lhd"/></glgps>'
        expected = original.replace(b'SensorsEnable="true"', b'SensorsEnable="false"')
        self.assertEqual(GNSS.receiver_config(original), expected)
        self.assertEqual(GNSS.receiver_config(expected), expected)

    def test_receiver_config_rejects_wrong_structure(self):
        for original in [b'<other/>', b'<glgps xmlns="http://www.glpals.com/"/>',
                         b'<glgps xmlns="http://www.glpals.com/"><hal/><hal/></glgps>']:
            with self.assertRaises(RuntimeError):
                GNSS.receiver_config(original)

    def run_children(self, daemon_code, client_code):
        daemon = subprocess.Popen([sys.executable, '-c', daemon_code])
        client = subprocess.Popen([sys.executable, '-c', client_code], stdout=subprocess.PIPE)
        try:
            return GNSS.watch_hal(daemon, client, True)
        finally:
            for child in (client, daemon):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=3)
            client.stdout.close()

    def test_dead_daemon_detected_while_hal_silent(self):
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, 'Vendor GNSS exited after HAL start: 17'):
            self.run_children('import time; time.sleep(.1); raise SystemExit(17)',
                              'import time; time.sleep(10)')
        self.assertLess(time.monotonic() - started, 3)

    def test_drain_status_burst_without_forwarding_location(self):
        output = io.StringIO()
        with contextlib.redirect_stderr(output):
            result = self.run_children(
                'import time; time.sleep(10)',
                "print('Standalone GNSS mode result: 0'); "
                "print('HAL start result: 0'); "
                "print('GNSS UTC injection result: 0'); "
                "print('GNSS position injection result: 0'); "
                "print('GNSS position injection result: latitude=12.3'); "
                "print('GNSS extension gps-xtra available: 1'); "
                "print('GNSS callbacks: status=2 satellites=1 nmea=14 location=0'); "
                "print('latitude=12.3 longitude=24.5')")
        self.assertEqual(result, 0)
        self.assertIn('GNSS HAL UTC assistance result: 0', output.getvalue())
        self.assertIn('gps-xtra available: 1', output.getvalue())
        self.assertIn('Standalone GNSS mode result: 0', output.getvalue())
        self.assertIn('HAL start result: 0', output.getvalue())
        self.assertIn('GNSS position injection result: 0', output.getvalue())
        self.assertIn('satellites=1 nmea=14', output.getvalue())
        self.assertNotIn('12.3', output.getvalue())
        self.assertNotIn('latitude', output.getvalue())

    def test_diagnostics_drop_locations_and_identifiers(self):
        for message in ['error latitude=12.3', 'receiver longitude=24.5',
                        'error IMEI=123456789', 'receiver token=private', '$GPGGA,nmea error']:
            self.assertIsNone(GNSS.diagnostic_message(b'head\0tag\0' + message.encode() + b'\0'))

    def test_diagnostics_redact_numbers_and_urls(self):
        result = GNSS.diagnostic_message(b'head\0tag\0receiver timeout 1234 https://example.com/secret\0')
        self.assertIn('receiver timeout', result)
        self.assertNotIn('1234', result)
        self.assertNotIn('secret', result)


if __name__ == '__main__':
    unittest.main()

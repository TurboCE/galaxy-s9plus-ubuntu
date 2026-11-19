# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/g965n/desktop-lte-service.py'
spec = importlib.util.spec_from_file_location('desktop_lte', SCRIPT)
desktop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(desktop)


class SimStartupTests(unittest.TestCase):
    def run_startup(self, response, stopping=lambda _: False, child_check=None):
        elapsed = 0

        def sleep(seconds):
            nonlocal elapsed
            elapsed += seconds

        with (patch.object(desktop.time, 'monotonic', side_effect=lambda: elapsed),
              patch.object(desktop.time, 'sleep', side_effect=sleep),
              patch.object(desktop, 'checked_children', side_effect=child_check),
              patch.object(desktop, 'read_sim_state', side_effect=lambda _: response(elapsed))):
            result = desktop.wait_for_sim(Mock(), Mock(), lambda: stopping(elapsed))
        return result, elapsed

    def test_only_sustained_absence_at_deadline_is_a_normal_skip(self):
        self.assertEqual(self.run_startup(lambda _: 'absent'), ('absent', 40))
        for response in (
            lambda _: 'unknown',
            lambda t: 'absent' if t < 39 else 'unknown',
            lambda t: 'absent' if t > 38 else 'unknown',
        ):
            with self.assertRaisesRegex(RuntimeError, 'ready SIM'):
                self.run_startup(response)

    def test_ready_can_recover_from_initial_absence(self):
        self.assertEqual(
            self.run_startup(lambda t: 'ready' if t >= 8 else 'absent'),
            ('ready', 8),
        )

    def test_shutdown_and_child_failure_take_precedence(self):
        self.assertEqual(
            self.run_startup(lambda _: 'absent', stopping=lambda t: t >= 4),
            ('stopped', 4),
        )
        with self.assertRaisesRegex(RuntimeError, 'child exited'):
            self.run_startup(lambda _: 'absent', child_check=RuntimeError('child exited'))

    def test_wire_reply_requires_both_explicit_boolean_fields_for_absence(self):
        for raw, expected in (
            (b'{"sim_ready":true}', 'ready'),
            (b'{"sim_ready":false,"sim_absent":true}', 'absent'),
            (b'{"sim_ready":false}', 'unknown'),
            (b'{"sim_ready":0,"sim_absent":1}', 'unknown'),
            (b'{"sim_ready":true,"sim_absent":true}', 'unknown'),
            (b'{"error":"unsupported-query"}', 'unknown'),
        ):
            with patch.object(desktop.socket, 'socket') as factory:
                sock = factory.return_value.__enter__.return_value
                sock.recv.return_value = raw
                self.assertEqual(desktop.read_sim_state(Mock()), expected)
                sock.sendall.assert_called_once_with(b'sim-readiness')

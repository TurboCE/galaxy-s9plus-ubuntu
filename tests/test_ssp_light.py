# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import struct
import signal
import unittest
from unittest.mock import patch, mock_open

spec = importlib.util.spec_from_file_location('ssp_probe',
    Path(__file__).resolve().parents[1] / 'experiments/sensors/ssp-probe.py')
ssp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssp)


class LightFrameTests(unittest.TestCase):
    def probe(self, layout):
        p = ssp.Probe.__new__(ssp.Probe)
        p.formats = {9: ssp.LIGHT_LAYOUTS[layout]}
        p.samples = {9: []}
        p.unparsed = 0
        return p

    def test_lux18_keeps_lux_cct_channels_and_timestamp_boundaries(self):
        p = self.probe('lux18')
        values = (250, 5500, 11, 22, 33, 44, 50, 8)
        frame = b'\x37\x09' + struct.pack('<IiHHHHBB', *values) + b'\0'*8
        p.records(frame + frame)
        self.assertEqual(p.samples[9], [values, values])
        self.assertEqual(ssp.light_fields(values, 'lux18')['hub_lux'], 250)
        self.assertEqual(p.unparsed, 0)

    def test_truncated_or_wrong_sensor_does_not_produce_a_sample(self):
        for frame in (b'\x37\x09' + b'\0'*25, b'\x37\x08' + b'\0'*26):
            p = self.probe('lux18'); p.records(frame)
            self.assertEqual(p.samples[9], [])
            self.assertEqual(p.unparsed, 1)

    def test_two_byte_gain_layout_is_explicit(self):
        p = self.probe('lux19')
        values = (100, 5000, 1, 2, 3, 4, 1024, 50)
        p.records(b'\x37\x09' + struct.pack('<IiHHHHHB', *values) + b'\0'*8)
        self.assertEqual(ssp.light_fields(p.samples[9][0], 'lux19')['gain'], 1024)

    def test_invalid_trailing_record_discards_the_whole_packet(self):
        values = (100, 5000, 1, 2, 3, 4, 50, 8)
        valid = b'\x37\x09' + struct.pack('<IiHHHHBB', *values) + b'\0'*8
        for tail in (b'\x03\x05\0x', b'\x03\0\0', b'\x05\x01', b'\x05\x01\xff'):
            p = self.probe('lux18')
            self.assertFalse(p.records(valid + tail))
            self.assertEqual(p.samples[9], [])
            self.assertEqual(p.unparsed, 1)

    def test_valid_debug_and_metadata_keep_the_packet_aligned(self):
        p = self.probe('lux18')
        values = (100, 5000, 1, 2, 3, 4, 50, 8)
        data = b'\x03\x03\0abc\x05\x01\x09\x37\x09' + struct.pack('<IiHHHHBB', *values) + b'\0'*8
        self.assertTrue(p.records(data))
        self.assertEqual(p.samples[9], [values])


class SamplingGuards(unittest.TestCase):
    def test_bounded_stop_raises_so_sensor_cleanup_can_run(self):
        with self.assertRaises(SystemExit) as stopped:
            ssp.terminate_probe(signal.SIGTERM, None)
        self.assertEqual(stopped.exception.code, 128 + signal.SIGTERM)

    def test_unexpected_hub_identity_refuses_sensor_enable(self):
        ssp.require_hub(0x55)
        for chip in (0, 0x54, 0xFF):
            with self.assertRaisesRegex(RuntimeError, 'no sensor enabled'):
                ssp.require_hub(chip)

    def test_zero_samples_or_missing_sensor_cannot_complete_sampling(self):
        self.assertFalse(ssp.sampling_complete([9], 1 << 9, {9: []}))
        self.assertFalse(ssp.sampling_complete([9], 0, {9: [(1,)]}))
        self.assertTrue(ssp.sampling_complete([9], 1 << 9, {9: [(1,)]}))

    def test_cleanup_attempts_every_enabled_sensor_and_fails_closed(self):
        class Probe:
            calls = []

            def transaction(self, command, payload):
                sensor = payload[0]
                self.calls.append((command, sensor))
                if sensor == 0:
                    raise RuntimeError('test timeout')

        p = Probe()
        with self.assertRaisesRegex(RuntimeError, 'disable failed'):
            ssp.disable_sensors(p, [0, 1, 9])
        self.assertEqual(p.calls, [(0xA2, 0), (0xA2, 1), (0xA2, 9)])

    def test_board_check_rejects_missing_or_lookalike_compatible(self):
        with patch.object(ssp.Path, 'read_bytes', return_value=b'samsung,star2lte-other\0'):
            with self.assertRaises(SystemExit):
                ssp.require_board()
        with patch.object(ssp.Path, 'read_bytes', side_effect=OSError('missing')):
            with self.assertRaises(SystemExit):
                ssp.require_board()
        with patch.object(ssp.Path, 'read_bytes', return_value=b'samsung,star2lte\0samsung,exynos9810\0'):
            ssp.require_board()


class AwakeNotificationTests(unittest.TestCase):
    def probe(self):
        p = ssp.Probe.__new__(ssp.Probe)
        p.fd = 123
        p.pending = None
        p.sequence = 7
        p.pump = lambda _: None
        return p

    def test_exact_zero_length_headers_without_reply_wait_or_sequence_claim(self):
        p = self.probe()
        with patch.object(ssp.os, 'write', return_value=9) as write, \
             patch.object(ssp.time, 'monotonic', side_effect=[0, .2, 1, 1.2]):
            p.notify_ap_awake()
        headers = [struct.unpack('<BHHI', call.args[1]) for call in write.call_args_list]
        self.assertEqual(headers, [(0xD1, 0, 1, 0), (0xD3, 0, 1, 0)])
        self.assertEqual(p.sequence, 7)
        self.assertIsNone(p.pending)

    def test_pending_transaction_prevents_notification(self):
        p = self.probe(); p.pending = (8, b'')
        with patch.object(ssp.os, 'write') as write, self.assertRaises(RuntimeError):
            p.notify_ap_awake()
        write.assert_not_called()

    def test_short_header_stops_before_sending_the_next_notification(self):
        p = self.probe()
        with patch.object(ssp.os, 'write', return_value=8) as write, self.assertRaisesRegex(RuntimeError, 'Short AP'):
            p.notify_ap_awake()
        self.assertEqual(write.call_count, 1)


class StartupReadinessTests(unittest.TestCase):
    class Clock:
        now = 0

        def pump(self, seconds):
            self.now += seconds

    def run_identity(self, outcomes, ready=None):
        clock = self.Clock()
        calls = []
        outcomes = iter(outcomes)

        class Probe:
            pump = clock.pump

            def transaction(self, command, length=0):
                calls.append((command, length, clock.now))
                if command == 0x0F:
                    value = next(outcomes)
                    if isinstance(value, Exception):
                        clock.now += 2
                        raise value
                    return bytes((value,))
                return (21031900 if command == 0xF0 else 1 << 9).to_bytes(length, 'little')

        self.calls = calls
        self.clock = clock
        with patch.object(ssp.time, 'monotonic', side_effect=lambda: clock.now), \
             patch.object(ssp, 'require_transport_ready', side_effect=ready):
            return ssp.acquire_hub_identity(Probe())

    def test_startup_timeout_then_valid_identity_only_retries_identity(self):
        result = self.run_identity([RuntimeError('No valid sensor reply for command 0xf'), 0x55])
        self.assertEqual(result['chip_id'], 0x55)
        self.assertEqual([c[:2] for c in self.calls], [(0x0F, 1), (0x0F, 1), (0xF0, 4), (0xF4, 8)])
        self.assertAlmostEqual(self.calls[0][2], 5)
        self.assertAlmostEqual(self.calls[1][2], 8)

    def test_real_transactions_keep_increasing_sequence_after_startup_timeout(self):
        clock = self.Clock()
        probe = ssp.Probe.__new__(ssp.Probe)
        probe.fd = 123; probe.sequence = 0; probe.pending = None; probe.reply = None

        def pump(seconds):
            clock.pump(seconds)
            if probe.pending and probe.sequence > 1:
                size = {2: 1, 3: 4, 4: 8}[probe.sequence]
                probe.reply = (0x55 if size == 1 else 1).to_bytes(size, 'little')

        probe.pump = pump
        with patch.object(ssp.time, 'monotonic', side_effect=lambda: clock.now), \
             patch.object(ssp, 'require_transport_ready'), patch.object(ssp.os, 'write', return_value=9) as write:
            self.assertEqual(ssp.acquire_hub_identity(probe)['chip_id'], 0x55)
        headers = [struct.unpack('<BHHI', call.args[1]) for call in write.call_args_list]
        self.assertEqual([h[0] for h in headers], [0x0F, 0x0F, 0xF0, 0xF4])
        self.assertEqual([h[2] >> 3 for h in headers], [1, 2, 3, 4])

    def test_malformed_actual_reply_has_distinct_nonretryable_error(self):
        clock = self.Clock()
        probe = ssp.Probe.__new__(ssp.Probe)
        probe.fd = 123; probe.sequence = 0; probe.pending = None; probe.reply = None

        def pump(seconds):
            clock.pump(seconds)
            if probe.pending:
                probe.reply = b'\x55\x55'

        probe.pump = pump
        with patch.object(ssp.time, 'monotonic', side_effect=lambda: clock.now), \
             patch.object(ssp, 'require_transport_ready'), patch.object(ssp.os, 'write', return_value=9) as write, \
             self.assertRaisesRegex(RuntimeError, 'Invalid sensor reply length'):
            ssp.acquire_hub_identity(probe)
        self.assertEqual(write.call_count, 1)

    def test_wrong_chip_never_retries_or_requests_firmware(self):
        with self.assertRaisesRegex(RuntimeError, 'Unexpected sensor hub'):
            self.run_identity([0x54, 0x55])
        self.assertEqual(len(self.calls), 1)

    def test_not_ready_during_settling_sends_nothing(self):
        checks = 0

        def ready():
            nonlocal checks
            checks += 1
            if checks == 3:
                raise RuntimeError('Hub transport not ready')

        with self.assertRaisesRegex(RuntimeError, 'not ready'):
            self.run_identity([0x55], ready)
        self.assertEqual(self.calls, [])

    def test_timeout_retries_are_bounded_to_three_and_thirteen_seconds(self):
        with self.assertRaisesRegex(RuntimeError, 'No valid sensor reply'):
            self.run_identity([RuntimeError('No valid sensor reply for command 0xf')] * 3)
        self.assertEqual(len(self.calls), 3)
        self.assertAlmostEqual(self.clock.now, 13)

    def test_short_write_and_malformed_reply_are_not_retried(self):
        for error in ['Short sensor header write', 'Invalid sensor reply length for command 0xf',
                      'Malformed sensor transport', 'No valid sensor reply for command 0xf extra']:
            with self.subTest(error=error), self.assertRaisesRegex(RuntimeError, error):
                self.run_identity([RuntimeError(error), 0x55])
            self.assertEqual(len(self.calls), 1)

    def test_identity_failure_in_main_never_enables_or_notifies(self):
        class Probe:
            fd = 123
            calls = []

            def __init__(self, _layout):
                pass

            def transaction(self, *args, **kwargs):
                self.calls.append((args, kwargs))

            def notify_ap_awake(self):
                self.calls.append('AP-awake')

        with patch.object(ssp, 'Probe', Probe), patch.object(ssp, 'require_board'), \
             patch.object(ssp.Path, 'read_text', return_value='1'), \
             patch.object(ssp, 'acquire_hub_identity', side_effect=RuntimeError('identity failed')), \
             patch('builtins.open', mock_open()), patch.object(ssp.fcntl, 'flock'), \
             patch.object(ssp.signal, 'signal'), patch.object(ssp.os, 'close') as close, \
             patch('sys.argv', ['ssp-probe', '--sample-seconds', '5', '--ap-awake']), \
             self.assertRaisesRegex(RuntimeError, 'identity failed'):
            ssp.main()
        self.assertEqual(Probe.calls, [])
        close.assert_called_once_with(123)

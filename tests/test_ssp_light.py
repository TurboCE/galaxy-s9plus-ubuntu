# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import struct
import signal
import unittest
from unittest.mock import patch

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

# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import struct
import signal
import io
import json
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


class SamplingPhaseTests(unittest.TestCase):
    def test_each_sensor_discards_earlier_startup_and_snapshots_are_independent(self):
        class Probe:
            samples = {0: [(100,)], 9: [(200,)]}
            calls = []

            def transaction(self, command, payload):
                sensor = payload[0]
                self.calls.append((command, sensor))
                self.samples[sensor].append((sensor + 1,))
                if sensor == 0:
                    self.samples[9].append((999,))  # received before light A1

        p = Probe(); enabled = []
        counts, initial = ssp.enable_sampling_phases(p, [0, 9], (1 << 0) | (1 << 9), enabled)
        self.assertEqual(counts, {'0': 1, '9': 2})
        self.assertEqual(initial, {0: [(1,)], 9: [(10,)]})
        self.assertEqual(p.samples, {0: [], 9: []})
        p.samples[9].append((20,))
        self.assertEqual(initial[9], [(10,)])
        self.assertEqual(enabled, [0, 9])
        self.assertEqual(p.calls, [(0xA1, 0), (0xA1, 9)])

    def run_main(self, initial_report=False, window_report=False):
        clock = StartupReadinessTests.Clock(); clock.now = 100
        sample = (250, 5500, 11, 22, 33, 44, 50, 8)

        class Probe:
            fd = 123
            calls = []
            unparsed = 0

            def __init__(self, _layout):
                self.samples = {9: [sample] * 4}

            def transaction(self, command, payload):
                self.calls.append(command)
                if command == 0xA1:
                    clock.now += .5
                    if initial_report:
                        self.samples[9].append(sample)

            def pump(self, seconds):
                clock.pump(seconds)
                if window_report:
                    self.samples[9].append((350,) + sample[1:])

        output = io.StringIO(); exit_code = 0
        with patch.object(ssp, 'Probe', Probe), patch.object(ssp, 'require_board'), \
             patch.object(ssp.Path, 'read_text', return_value='1'), \
             patch.object(ssp, 'acquire_hub_identity', return_value={'chip_id': 0x55, 'firmware': 1, 'sensor_mask': 1 << 9}), \
             patch('builtins.open', mock_open()), patch.object(ssp.fcntl, 'flock'), \
             patch.object(ssp.signal, 'signal'), patch.object(ssp.os, 'close'), \
             patch.object(ssp.time, 'monotonic', side_effect=lambda: clock.now), \
             patch('sys.stdout', output), \
             patch('sys.argv', ['ssp-probe', '--sensors', 'light', '--light-layout', 'lux18', '--sample-seconds', '2', '--stream']):
            try:
                ssp.main()
            except SystemExit as error:
                exit_code = error.code
        text = output.getvalue(); start = text.index('\n{\n')
        streams = [json.loads(line) for line in text[:start].splitlines()]
        return exit_code, json.loads(text[start+1:]), streams, Probe.calls

    def test_startup_only_cannot_qualify_enable_or_measurement(self):
        code, result, streams, calls = self.run_main()
        self.assertEqual(code, 2)
        self.assertEqual(result['startup_sample_counts'], {'9': 4})
        self.assertEqual(result['enable_samples']['9']['count'], 0)
        self.assertEqual(result['samples']['9']['count'], 0)
        self.assertFalse(result['sampling_window_complete'])
        self.assertFalse(result['sampling_complete'])
        self.assertTrue(all(row['light_count'] == 0 and row['light'] is None for row in streams))
        self.assertEqual(calls, [0xA1, 0xA2])

    def test_on_change_initial_report_is_separate_from_empty_window(self):
        code, result, streams, calls = self.run_main(initial_report=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['enable_samples']['9']['count'], 1)
        self.assertEqual(result['samples']['9']['count'], 0)
        self.assertTrue(result['sampling_complete'])
        self.assertFalse(result['sampling_window_complete'])
        self.assertTrue(all(row['light_count'] == 0 for row in streams))
        self.assertEqual(calls, [0xA1, 0xA2])

    def test_window_counts_and_elapsed_start_after_enable_phase(self):
        code, result, streams, calls = self.run_main(initial_report=True, window_report=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['startup_sample_counts']['9'], 4)
        self.assertEqual(result['enable_samples']['9']['count'], 1)
        self.assertGreater(result['samples']['9']['count'], 1)
        self.assertEqual(result['enable_samples']['9']['first'][0], 250)
        self.assertEqual(result['samples']['9']['first'][0], 350)
        self.assertTrue(result['sampling_window_complete'])
        self.assertLess(result['measurement_window_seconds'], 2.11)
        self.assertGreaterEqual(result['measurement_window_seconds'], 2)
        self.assertTrue(all(1 <= row['elapsed_s'] <= 2.1 for row in streams))
        self.assertEqual(calls, [0xA1, 0xA2])


class ExtendedSensorFrames(unittest.TestCase):
    def probe(self):
        p = ssp.Probe.__new__(ssp.Probe)
        p.formats = dict(ssp.SENSOR_FORMATS)
        p.samples = {sensor: [] for sensor in p.formats}
        p.unparsed = 0
        return p

    def test_pinned_signed_fields_overflow_and_timestamp_alignment(self):
        cases = {2: (-1, 2, -3, 4, -5, 6, 1), 3: (-7, 8, -9),
                 4: (-10, 11, -12, 3, 1), 5: (101325, -250),
                 7: (1, 65530), 10: (65531,)}
        p = self.probe()
        data = b''.join(bytes([0x37, sensor]) + struct.pack(p.formats[sensor], *values)
                        + bytes([0xFF])*8 for sensor, values in cases.items())
        self.assertTrue(p.records(data))
        for sensor, values in cases.items():
            self.assertEqual(p.samples[sensor], [values])

    def test_every_extended_truncated_frame_is_atomic(self):
        for sensor in (2, 3, 4, 5, 7, 10):
            p = self.probe()
            frame = bytes([0x37, sensor]) + bytes(struct.calcsize(p.formats[sensor]) + 7)
            self.assertFalse(p.records(frame))
            self.assertEqual(p.samples[sensor], [])

    def test_missing_mask_refuses_selection_before_enable(self):
        for sensor in (2, 3, 4, 5, 7, 10):
            with self.assertRaisesRegex(RuntimeError, 'does not advertise'):
                ssp.require_advertised([sensor], 0)
            ssp.require_advertised([sensor], 1 << sensor)
        self.assertEqual(ssp.SENSOR_GROUPS['all'], [0, 1, 9])

    def test_extended_phases_and_cleanup_preserve_sensor_ids(self):
        class Probe:
            def __init__(self):
                self.samples = {s: [(99,)] for s in (4, 5, 7)}
                self.calls = []
            def transaction(self, command, payload):
                self.calls.append((command, payload[0]))
                if command == 0xA1:
                    self.samples[payload[0]].append((1,))
        p = Probe(); enabled = []
        startup, initial = ssp.enable_sampling_phases(p, [4, 5, 7], sum(1<<s for s in (4,5,7)), enabled)
        self.assertEqual(startup, {'4': 1, '5': 1, '7': 1})
        self.assertEqual(initial, {4: [(1,)], 5: [(1,)], 7: [(1,)]})
        self.assertEqual(p.samples, {4: [], 5: [], 7: []})
        ssp.disable_sensors(p, enabled)
        self.assertEqual(p.calls[-3:], [(0xA2,4), (0xA2,5), (0xA2,7)])


class MagneticFuseTests(unittest.TestCase):
    def test_read_is_exact_command_length_and_no_write_payload(self):
        class Probe:
            def transaction(self, command, **kwargs):
                self.call = (command, kwargs)
                return bytes([128, 129, 130])
        p = Probe()
        self.assertEqual(ssp.read_magnetic_fuse(p, 1 << 2),
                         {'bytes': [128,129,130], 'valid_factory_bytes': True})
        self.assertEqual(p.call, (1, {'length': 3}))
        self.assertEqual(ssp.SENSOR_GROUPS['compass'], [4])
        self.assertEqual(ssp.SENSOR_GROUPS['magnetic-calibrated'], [4])
        self.assertEqual(ssp.SENSOR_GROUPS['magnetic-uncalibrated'], [2])
        self.assertEqual(ssp.SENSOR_GROUPS['magnetic-raw'], [3])

    def test_unsupported_never_transactions_and_invalid_fuse_stays_invalid(self):
        class Probe:
            calls = 0
            def transaction(self, *args, **kwargs):
                self.calls += 1
                return b'\0\xff\x80'
        p = Probe()
        with self.assertRaisesRegex(RuntimeError, 'does not advertise'):
            ssp.read_magnetic_fuse(p, 0)
        self.assertEqual(p.calls, 0)
        self.assertFalse(ssp.read_magnetic_fuse(p, 1 << 2)['valid_factory_bytes'])

    def test_read_failure_propagates_without_fallback(self):
        class Probe:
            def transaction(self, *args, **kwargs):
                raise RuntimeError('Invalid sensor reply length for command 0x1')
        with self.assertRaisesRegex(RuntimeError, 'Invalid sensor reply length'):
            ssp.read_magnetic_fuse(Probe(), 1 << 2)


class RotationThermalTests(unittest.TestCase):
    def test_packed_raw_formats_and_multi_record_boundaries(self):
        p = ssp.Probe.__new__(ssp.Probe)
        p.formats = dict(ssp.SENSOR_FORMATS)
        p.samples = {sensor: [] for sensor in p.formats}; p.unparsed = 0
        cases = {16: (-2147483648, 2, -3, 2147483647, 255),
                 17: (4, -5, 6, -7, 2), 34: (255, -32768)}
        data = b''.join(bytes([0x37, sensor]) + struct.pack(p.formats[sensor], *values)
                        + bytes(range(8)) for sensor, values in cases.items())
        self.assertTrue(p.records(data))
        for sensor, values in cases.items():
            self.assertEqual(p.samples[sensor], [values])
        self.assertEqual(ssp.SENSOR_GROUPS['thermal'], [34])
        self.assertEqual(ssp.SENSOR_GROUPS['rotation'], [16,17])

    def test_truncation_does_not_qualify_raw_samples(self):
        for sensor in (16, 17, 34):
            p = ssp.Probe.__new__(ssp.Probe)
            p.formats = dict(ssp.SENSOR_FORMATS)
            p.samples = {sensor: []}; p.unparsed = 0
            self.assertFalse(p.records(bytes([0x37,sensor]) + bytes(struct.calcsize(p.formats[sensor])+7)))
            self.assertFalse(ssp.sampling_complete([sensor], 1<<sensor, p.samples))

    def test_startup_clear_window_and_cleanup_for_high_sensor_ids(self):
        class Probe:
            def __init__(self):
                self.samples = {s: [(999,)] for s in (16,17,34)}
                self.calls = []
            def transaction(self, command, payload):
                self.calls.append((command, payload[0]))
                if command == 0xA1:
                    self.samples[payload[0]].append((1,))
        p = Probe(); enabled = []
        selected = [16,17,34]; mask = sum(1<<s for s in selected)
        ssp.require_advertised(selected, mask)
        counts, initial = ssp.enable_sampling_phases(p, selected, mask, enabled)
        self.assertEqual(counts, {'16':1,'17':1,'34':1})
        self.assertTrue(ssp.sampling_complete(selected, mask, initial))
        self.assertFalse(ssp.sampling_complete(selected, mask, p.samples))
        with self.assertRaises(RuntimeError):
            ssp.require_advertised(selected, mask ^ (1<<34))
        ssp.disable_sensors(p, enabled)
        self.assertEqual(p.calls[-3:], [(0xA2,16),(0xA2,17),(0xA2,34)])

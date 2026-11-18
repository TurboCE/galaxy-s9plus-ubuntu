# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gpu_validation',
    Path(__file__).resolve().parents[1] / 'scripts/g965n/gpu-validate.py')
gpu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gpu)


class GPUAcceptanceTests(unittest.TestCase):
    def test_display_dma_failure_fails_even_without_panfrost_fault(self):
        self.assertRegex('s9p-decon 16030000.decon: swiotlb buffer is full (sz: 2097152 bytes)', gpu.FAULT)
        self.assertRegex('panfrost 17500000.gpu: js0 timeout', gpu.FAULT)
        self.assertRegex('[CRTC:38:crtc-0] vblank wait timed out', gpu.FAULT)
        self.assertRegex('[CRTC:38:crtc-0] flip_done timed out', gpu.FAULT)
        self.assertIsNone(gpu.FAULT.search('panfrost 17500000.gpu: AARCH64_4K page tables'))


class FIFOPresentationTests(unittest.TestCase):
    def output(self, fps):
        return '\n'.join(f'[{name}] duration=4: FPS: {fps} FrameTime: 1 ms'
                         for name in ['build', 'texture', 'ideas']) + '\nglmark2 Score: 2000'

    def test_high_unconstrained_score_does_not_hide_half_rate_fifo(self):
        self.assertFalse(gpu.fifo_result(self.output(31))['cadence_pass'])
        self.assertTrue(gpu.fifo_result(self.output(60))['cadence_pass'])

    def test_missing_or_duplicate_scene_cannot_qualify(self):
        self.assertFalse(gpu.fifo_result(self.output(60).replace('[ideas]', '[build]'))['complete'])
        self.assertFalse(gpu.fifo_result(self.output(60).replace('glmark2 Score:', 'incomplete:'))['complete'])


class ProfileTests(unittest.TestCase):
    def output(self):
        return '\n'.join(f'[{name}] {options}: FPS: 300 FrameTime: 3 ms'
                         for name, options in gpu.TARGETED) + '\nglmark2 Score: 300'

    def test_targeted_requires_exact_three_complete_scenes(self):
        self.assertTrue(gpu.scene_result(self.output(), 'targeted')['complete'])
        for output in (self.output().replace('[loop]', '[buffer]'),
                       self.output().replace('duration=8', 'duration=1'),
                       self.output().replace('glmark2 Score:', 'incomplete:'),
                       self.output().split('[loop]')[0],
                       self.output() + '\n[loop] duration=8: FPS: 300'):
            with self.subTest(output=output):
                self.assertFalse(gpu.scene_result(output, 'targeted')['complete'])

    def test_partial_scene_line_cannot_pass(self):
        for tail in ('FPS:', 'FPS: 300', 'FPS: 300 FrameTime:'):
            output = self.output().replace('vertex-steps=5:duration=8: FPS: 300 FrameTime: 3 ms',
                                           'vertex-steps=5:duration=8: ' + tail)
            self.assertFalse(gpu.scene_result(output, 'targeted')['complete'])

    def test_zero_nonfinite_and_malformed_fps_fail_without_exception(self):
        for value in ('0', '0.0', '..', '1.2.3', 'nan', 'inf', '9' * 400):
            with self.subTest(fps=value):
                self.assertFalse(gpu.scene_result(self.output().replace('FPS: 300', 'FPS: ' + value),
                                                 'targeted')['complete'])

    def test_full_defaults_and_targeted_bounds(self):
        full = gpu.commands_for('full', Path('/fixture/readback'), '512x512', True)
        self.assertEqual([item[0] for item in full], ['readback', 'scenes', 'fifo'])
        self.assertEqual([item[2] for item in full], [30, 90, 30])
        self.assertEqual(full[1][1][-2:], ['--benchmark', ':duration=1'])
        targeted = gpu.commands_for('targeted', None, '1440x2960')
        self.assertEqual(len(targeted), 1)
        self.assertEqual(targeted[0][2], 45)
        self.assertEqual(targeted[0][1].count('-b'), 3)
        self.assertTrue(all(':duration=8' in arg for arg in targeted[0][1] if arg.startswith(('buffer:', 'function:', 'loop:'))))
        self.assertFalse(gpu.scene_result(self.output(), 'full')['complete'])


    def test_fullscreen_keeps_readback_and_deadlines_but_replaces_window_size(self):
        full = gpu.commands_for('full', Path('/fixture/readback'), '512x512', True, True)
        targeted = gpu.commands_for('targeted', None, '1440x2960', False, True)
        self.assertEqual(full[0], gpu.commands_for('full', Path('/fixture/readback'), '512x512')[0])
        self.assertEqual([item[2] for item in full], [30, 90, 30])
        self.assertEqual(targeted[0][2], 45)
        for _, command, _ in full[1:] + targeted:
            self.assertIn('--fullscreen', command)
            self.assertNotIn('--size', command)


class TimedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.timeline = Path(self.temp.name) / 'timeline.jsonl'
        self.protocol = Path(self.temp.name) / 'protocol.log'

    def rows(self):
        return [json.loads(line) for line in self.timeline.read_text().splitlines()]

    def test_success_records_lines_partial_tail_and_real_exit(self):
        code, output = gpu.run([sys.executable, '-c',
            "import sys; print('first'); sys.stdout.write('tail'); sys.exit(7)"],
            dict(os.environ), 3, self.timeline, 'fixture')
        self.assertEqual((code, output), (7, 'first\ntail'))
        rows = self.rows()
        self.assertEqual([row['event'] for row in rows], ['start', 'line', 'line', 'finish'])
        self.assertTrue(rows[2]['partial'])
        self.assertFalse(rows[-1]['timed_out'])
        self.assertTrue(all(row['command'] == 'fixture' for row in rows))

    def check_timeout(self, script, expected):
        processes = []
        original = subprocess.Popen

        def capture(*args, **kwargs):
            child = original(*args, **kwargs); processes.append(child); return child

        start = time.monotonic()
        with patch.object(gpu.subprocess, 'Popen', side_effect=capture):
            code, output = gpu.run([sys.executable, '-c', script], dict(os.environ),
                                   0.25, self.timeline, 'timeout-fixture')
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(code, 124)
        self.assertIn(expected, output)
        self.assertIn('QUALIFICATION_TIMEOUT', output)
        self.assertIsNotNone(processes[0].returncode)
        self.assertTrue(processes[0].stdout.closed)
        self.assertTrue(self.rows()[-1]['timed_out'])

    def test_silent_child_is_killed_and_reaped_on_deadline(self):
        self.check_timeout('import time; time.sleep(20)', '')

    def test_partial_line_never_blocks_deadline(self):
        self.check_timeout("import sys,time; sys.stdout.write('partial'); sys.stdout.flush(); time.sleep(20)", 'partial')
        line = next(row for row in self.rows() if row['event'] == 'line')
        self.assertTrue(line['partial'])

    def test_closed_output_still_waits_with_deadline_and_cleans_child(self):
        self.check_timeout('import os,time; os.close(1); os.close(2); time.sleep(20)', '')

    def test_descendant_holding_output_cannot_extend_deadline(self):
        self.check_timeout("import subprocess,sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])", '')

    def test_separate_large_no_newline_stderr_preserves_partial_stdout_scene(self):
        expected = ProfileTests().output()
        script = ("import sys; s=" + repr(expected) + "; "
                  "sys.stdout.write(s[:7]); sys.stdout.flush(); "
                  "sys.stderr.write('x'*524288); sys.stderr.flush(); "
                  "sys.stdout.write(s[7:]); sys.stdout.flush()")
        code, output = gpu.run([sys.executable, '-c', script], dict(os.environ), 3,
                               self.timeline, 'separate-fixture', self.protocol)
        self.assertEqual((code, output), (0, expected))
        self.assertEqual(self.protocol.stat().st_size, 524288)
        self.assertTrue(gpu.scene_result(output, 'targeted')['complete'])
        self.assertNotIn('x' * 100, self.timeline.read_text())

    def test_separate_stderr_timeout_kills_reaps_and_closes_both_streams(self):
        processes = []
        original = subprocess.Popen

        def capture(*args, **kwargs):
            child = original(*args, **kwargs); processes.append(child); return child

        script = ("import sys,time; sys.stdout.write('partial'); sys.stdout.flush(); "
                  "sys.stderr.write('x'*524288); sys.stderr.flush(); time.sleep(20)")
        start = time.monotonic()
        with patch.object(gpu.subprocess, 'Popen', side_effect=capture):
            code, output = gpu.run([sys.executable, '-c', script], dict(os.environ), 0.25,
                                   self.timeline, 'stderr-timeout', self.protocol)
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(code, 124)
        self.assertIn('partial', output)
        self.assertNotIn('x' * 100, output)
        self.assertGreater(self.protocol.stat().st_size, 0)
        self.assertIsNotNone(processes[0].returncode)
        self.assertTrue(processes[0].stdout.closed)
        self.assertTrue(processes[0].stderr.closed)

    def test_silent_separate_stderr_needs_no_timeline_and_keeps_deadline(self):
        code, output = gpu.run([sys.executable, '-c', 'import time; time.sleep(20)'],
                               dict(os.environ), 0.25, protocol=self.protocol)
        self.assertEqual(code, 124)
        self.assertIn('QUALIFICATION_TIMEOUT', output)
        self.assertEqual(self.protocol.stat().st_size, 0)
        self.assertFalse(self.timeline.exists())

    def test_wayland_debug_override_is_only_on_explicit_glmark_child(self):
        env = dict(os.environ, WAYLAND_DEBUG='server')
        with patch.object(gpu, 'run_timed', return_value=(0, '')) as run:
            gpu.run(['glmark2-es2-wayland'], env, 3, protocol=self.protocol)
        self.assertEqual(run.call_args.args[1]['WAYLAND_DEBUG'], 'client')
        self.assertEqual(env['WAYLAND_DEBUG'], 'server')
        with patch.object(gpu, 'run_timed', return_value=(0, '')) as run:
            gpu.run(['/fixture/readback'], env, 3, self.timeline)
        self.assertEqual(run.call_args.args[1]['WAYLAND_DEBUG'], 'server')
        with patch.object(gpu.subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([], 0, '')
            gpu.run(['glmark2-es2-wayland'], env, 3)
        self.assertEqual(run.call_args.kwargs['env']['WAYLAND_DEBUG'], 'server')

# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import unittest

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

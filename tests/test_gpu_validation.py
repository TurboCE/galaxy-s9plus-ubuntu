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
        self.assertIsNone(gpu.FAULT.search('panfrost 17500000.gpu: AARCH64_4K page tables'))

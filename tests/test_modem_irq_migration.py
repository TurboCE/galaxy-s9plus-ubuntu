# SPDX-License-Identifier: GPL-2.0-only
"""The stock comparison must permit only the qualified interrupt migration."""
import importlib.util
from pathlib import Path
import struct
import unittest

path = Path(__file__).resolve().parents[1] / 'experiments/modem/verify-overlay.py'
spec = importlib.util.spec_from_file_location('overlay_verify', path)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def node(*cells):
    return {'': {'interrupts': struct.pack('>' + 'I' * len(cells), *cells)}}


class InterruptMigration(unittest.TestCase):
    def test_exact_known_spis(self):
        for name, old, new in [
            ('mif_pdata', (0, 74, 0, 0, 440, 0), (0, 74, 4, 0, 440, 4)),
            ('mcu_ipc@14170000', (0, 69, 0), (0, 69, 4)),
        ]:
            a, b = node(*old), node(*new)
            self.assertTrue(verify.migrate_interrupts(name, a, b))
            self.assertEqual(a, b)

    def test_no_general_relaxation(self):
        for cells in [(0, 69, 0), (0, 69, 1), (0, 69, 8), (0, 70, 4),
                      (1, 69, 4), (0, 69), (0, 69, 4, 0)]:
            a = node(0, 69, 0)
            self.assertFalse(verify.migrate_interrupts('mcu_ipc@14170000', a, node(*cells)))
            self.assertEqual(a, node(0, 69, 0))
        self.assertFalse(verify.migrate_interrupts('mcu_ipc@14170000', node(0, 69, 1), node(0, 69, 4)))


if __name__ == '__main__':
    unittest.main()

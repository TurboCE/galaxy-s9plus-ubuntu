# SPDX-License-Identifier: GPL-2.0-only
import importlib.machinery
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / 'extras/debug-tools/files/usr/local/sbin/s9p-acpm'
loader = importlib.machinery.SourceFileLoader('acpm_tool', str(PATH))
module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(module)


class AcpmTests(unittest.TestCase):
    def test_import_does_not_map_device_memory(self):
        self.assertIsNone(module.sram)
        self.assertIsNone(module.mbox)

    def test_faulting_pages_and_invalid_offsets_are_not_dereferenced(self):
        with patch.object(module, 'sram', 1000000), patch.object(module, 'mbox', 2000000):
            for off in (0, 0x2ffc, 0x3001, module.SRAM_SIZE, -4):
                with self.subTest(offset=off), self.assertRaises(ValueError):
                    module.r32(module.sram, off)
            module.validate_access(module.sram, 0x3000)
            module.validate_access(module.sram, module.SRAM_SIZE - 4)

    def test_dvfs_query_never_changes_touch_power(self):
        with patch.object(module, 'find_channel', return_value=object()), \
             patch.object(module, 'send', return_value=1), \
             patch.object(module, 'receive', return_value=[0, 1000000, 0, 0]), \
             patch.object(module, 'mfd') as mfd:
            module.main(['dvfs', 'big'])
            mfd.assert_not_called()

    def test_touch_command_is_separate_and_requires_on_or_off(self):
        with patch.object(module, 'mfd', return_value=(0, 0, [0] * 4)) as mfd:
            module.main(['tsp', 'on'])
            writes = [call.args for call in mfd.call_args_list if call.args[0] == module.FUNC_UPDATE]
            self.assertEqual(len(writes), 2)
            self.assertTrue(all(args[3:] == (0xc0, 0xc0) for args in writes))
            with self.assertRaises(SystemExit):
                module.main(['tsp', 'invalid'])

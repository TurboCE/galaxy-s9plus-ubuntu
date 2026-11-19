# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parents[1]/'scripts/g965n/kernel-health.py'
s=importlib.util.spec_from_file_location('kh',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class KernelHealthTests(unittest.TestCase):
    def test_early_boot_missing_is_not_clean_kernel_or_private_output(self):
        logs={k:'' for k in m.COMMANDS}
        logs['ring']='Linux version test\nCPU: Unexpected variation in SYS_TEST\nprivate-subscriber-450081234567890\nMCU_RESP still high\n'
        logs['journal']='late module started\n'
        logs['ring-warnings']='warning\n'
        result=m.summary(logs)
        self.assertTrue(result['journal_early_boot_missing'])
        self.assertEqual(result['ring_error_priority_lines'],0)
        self.assertEqual(result['ring_warning_priority_lines'],1)
        self.assertEqual(result['known_message_counts']['cpu_register_variations'],1)
        self.assertFalse(result['all_hardware_qualified'])
        self.assertNotIn('450081234567890',json.dumps(result))
        logs['ring']='late ring only\n'
        self.assertFalse(m.summary(logs)['ring_boot_header_present'])

    def test_exclusive_private_files_and_failed_capture_do_not_report_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve();p.chmod(0o700)
            m.write_private(p/'old','earlier evidence')
            self.assertEqual(stat.S_IMODE((p/'old').stat().st_mode),0o600)
            with self.assertRaises(FileExistsError):m.write_private(p/'old','overwrite')
            (p/'link').symlink_to(p/'old')
            with self.assertRaises(OSError):m.write_private(p/'link','bad')
            p.chmod(0o755)
            with self.assertRaises(ValueError):m.write_private(p/'open','bad')
            p.chmod(0o700)
            with patch.object(m.subprocess,'run',side_effect=RuntimeError('capture failed')):
                with self.assertRaises(RuntimeError):m.collect(p)
            self.assertFalse((p/'summary.json').exists())


if __name__=='__main__':unittest.main()

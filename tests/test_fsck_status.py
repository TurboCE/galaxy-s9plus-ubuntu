# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts/flash/flash_s9plus_rootfs_adb.py'
spec = importlib.util.spec_from_file_location('rootfs_writer', PATH)
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


class FsckTests(unittest.TestCase):
    def test_clean_or_repaired_filesystem_is_accepted(self):
        for status in (0, 1):
            with self.subTest(status=status):
                writer.validate_fsck_result(SimpleNamespace(
                    stdout=f'check output\nS9_FSCK_EXIT={status}\n', returncode=status))

    def test_inner_failure_cannot_be_hidden_by_successful_shell(self):
        for status in (2, 4, 8, 16, 32, 128):
            with self.subTest(status=status), self.assertRaises(SystemExit):
                writer.validate_fsck_result(SimpleNamespace(
                    stdout=f'S9_FSCK_EXIT={status}\n', returncode=0))

    def test_missing_status_or_transport_failure_stops_install(self):
        for output, code in [('TYPE=ext4\n', 0), ('S9_FSCK_EXIT=0\n', 255)]:
            with self.subTest(code=code), self.assertRaises(SystemExit):
                writer.validate_fsck_result(SimpleNamespace(stdout=output, returncode=code))

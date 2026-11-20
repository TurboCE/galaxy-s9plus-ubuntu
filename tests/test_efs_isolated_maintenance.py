# SPDX-License-Identifier: GPL-2.0-only
import contextlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

SPEC = importlib.util.spec_from_file_location('isolated_efs', Path(__file__).resolve().parents[1] / 'scripts/g965n/revalidate-private-efs.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MaintenanceLease(unittest.TestCase):
    def setUp(self):
        self.held = set()
        self.runtime = Mock(STATE_LOCK='state', RUNTIME_LOCK='runtime')
        self.runtime.assert_board = Mock()
        self.runtime.assert_modem_stopped = Mock()
        self.runtime.ROOT.is_mount.return_value = False
        self.runtime.fcntl.LOCK_EX = 2

        @contextlib.contextmanager
        def lease(path, mode):
            self.assertEqual(mode, 2)
            self.held.add(path)
            try:
                yield
            finally:
                self.held.remove(path)

        self.runtime.checked_lock.side_effect = lease
        self.args = SimpleNamespace(old_efs_backup=Path('/private/old'),
                                    efs_backup=Path('/private/new'),
                                    cpefs_backup=Path('/private/cpefs'),
                                    backup_manifest=Path('/private/manifest'))

    def test_proof_and_cleanup_hold_both_exclusive_leases(self):
        def check(*a, **kw):
            self.assertEqual(self.held, {'state', 'runtime'})
        self.runtime.prepare.side_effect = check
        self.runtime.revalidate_efs_superblock.side_effect = check
        self.runtime.teardown.side_effect = check
        MODULE.maintain(self.runtime, self.args)
        self.runtime.prepare.assert_called_once_with(create_devices=False)
        self.runtime.revalidate_efs_superblock.assert_called_once_with(
            self.args.old_efs_backup, self.args.efs_backup,
            self.args.cpefs_backup, self.args.backup_manifest, confirm=True)
        self.runtime.teardown.assert_called_once()
        self.assertFalse(self.held)

    def test_proof_failure_still_cleans_its_view_before_releasing_leases(self):
        self.runtime.revalidate_efs_superblock.side_effect = RuntimeError('synthetic proof refusal')
        self.runtime.teardown.side_effect = lambda: self.assertEqual(self.held, {'state', 'runtime'})
        with self.assertRaisesRegex(RuntimeError, 'proof refusal'):
            MODULE.maintain(self.runtime, self.args)
        self.runtime.teardown.assert_called_once()
        self.assertFalse(self.held)

    def test_occupied_view_is_preserved_without_prepare_or_teardown(self):
        self.runtime.ROOT.is_mount.return_value = True
        with self.assertRaisesRegex(RuntimeError, 'Existing modem runtime preserved'):
            MODULE.maintain(self.runtime, self.args)
        self.runtime.prepare.assert_not_called()
        self.runtime.revalidate_efs_superblock.assert_not_called()
        self.runtime.teardown.assert_not_called()
        self.assertFalse(self.held)


if __name__ == '__main__':
    unittest.main()

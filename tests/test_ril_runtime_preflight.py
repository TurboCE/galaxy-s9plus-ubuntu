# SPDX-License-Identifier: GPL-2.0-only
"""No modem power operation before private provenance and runtime checks."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from contextlib import nullcontext
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ril_launcher_test', ROOT/'scripts/g965n/run-ril-test.py')
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)

spec = importlib.util.spec_from_file_location('cbd_launcher_test', ROOT/'scripts/g965n/run-cbd-test.py')
cbd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cbd)


class RuntimePreflightTests(unittest.TestCase):
    def runtime(self):
        return SimpleNamespace(ROOT=Path('/fixture/runtime'), STATE=Path('/fixture/state'),
            DATA=Path('/fixture/state/data'), assert_board=MagicMock(),
            read_provenance=MagicMock(return_value={'fixture': True}),
            validate_modem_state=MagicMock(), verify_private_bindings=MagicMock(),
            shared_runtime_lock=lambda: nullcontext(), safe_components=MagicMock(), regular_info=MagicMock())

    def test_cbd_lifetime_lock_wraps_trace_outside_chroot(self):
        runtime = SimpleNamespace(RUNTIME_LOCK=Path('/run/g965n-vendor-runtime.lock'))
        for trace in (False, True):
            command = cbd.cbd_command(SimpleNamespace(trace=trace), runtime)
            self.assertEqual(command[:5], ['/usr/bin/flock', '--shared', '--nonblock',
                                          '--no-fork', str(runtime.RUNTIME_LOCK)])
            chroot = command.index('/usr/sbin/chroot')
            self.assertEqual(command[chroot+1], str(cbd.ROOT))
            self.assertEqual(command[chroot+2], '/vendor/bin/cbd')
            if trace:
                self.assertLess(command.index('/usr/bin/strace'), chroot)
            else:
                self.assertNotIn('/usr/bin/strace', command)

    def test_provenance_rejection_happens_before_modem_off(self):
        args = SimpleNamespace(apn='fixture.apn', lab_directory=ROOT/'experiments/modem',
            runtime_helper=ROOT/'scripts/g965n/vendor-runtime.py', seconds=30)
        with patch.object(launcher.argparse.ArgumentParser, 'parse_args', return_value=args), \
                patch.object(launcher.os, 'geteuid', return_value=0), \
                patch.object(Path, 'read_bytes', return_value=b'samsung,star2lte\0'), \
                patch.object(launcher.subprocess, 'run', return_value=SimpleNamespace(returncode=3)), \
                patch.object(launcher, 'load_runtime', return_value=self.runtime()), \
                patch.object(launcher, 'verify_private_runtime', side_effect=RuntimeError('bad provenance')), \
                patch.object(launcher.fcntl, 'ioctl') as ioctl:
            with self.assertRaisesRegex(RuntimeError, 'bad provenance'): launcher.main()
            ioctl.assert_not_called()

    def test_provenance_and_bind_validation_both_required(self):
        runtime = self.runtime()
        helper = ROOT/'scripts/g965n/vendor-runtime.py'
        self.assertIs(launcher.verify_private_runtime(helper, runtime), runtime)
        runtime.validate_modem_state.assert_called_with({'fixture': True})
        runtime.verify_private_bindings.assert_called_once()
        runtime.read_provenance.side_effect = RuntimeError('legacy refused')
        runtime.verify_private_bindings.reset_mock()
        with self.assertRaisesRegex(RuntimeError, 'legacy'):
            launcher.verify_private_runtime(helper, runtime)
        runtime.verify_private_bindings.assert_not_called()


if __name__ == '__main__': unittest.main()

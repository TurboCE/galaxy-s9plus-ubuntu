# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the production upload function without running device preflight."""
import ast
import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/flash/flash_s9plus_boot_adb.py'


class BootUpload(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.image = Path(self.directory.name) / 'fixture.img'
        self.data = b'synthetic boot fixture'
        self.image.write_bytes(self.data)
        self.digest = hashlib.sha256(self.data).hexdigest()
        functions = [n for n in ast.parse(SOURCE.read_text()).body
                     if isinstance(n, ast.FunctionDef) and n.name in ('upload_boot', 'require')]
        self.transport = Mock()
        self.process = Mock(SubprocessError=subprocess.SubprocessError)
        self.env = {'subprocess': self.process, 'adb': self.transport,
                    'ADB': 'fixture-adb', 'SERIAL': 'selected-fixture-device'}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), self.env)

    def upload(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.env['upload_boot'](self.image, '/tmp/fixture-boot.img', self.digest)

    def test_verified_staging_is_reused(self):
        self.transport.return_value = self.digest + '  /tmp/fixture-boot.img'
        self.upload()
        self.process.run.assert_not_called()
        self.assertEqual(self.transport.call_count, 1)

    def test_raw_transfer_is_selected_and_verified(self):
        self.transport.side_effect = [subprocess.CalledProcessError(1, 'fixture'), '', '', self.digest]
        payloads = []
        self.process.run.side_effect = lambda *a, **kw: payloads.append(kw['stdin'].read())
        self.upload()
        self.assertEqual(payloads, [self.data])
        args = self.process.run.call_args.args[0]
        self.assertEqual(args[:4], ['fixture-adb', '-s', 'selected-fixture-device', 'exec-in'])
        self.assertTrue(all('push' not in c.args for c in self.transport.call_args_list))

    def test_discarded_raw_stream_falls_back_and_rechecks(self):
        self.transport.side_effect = ['', '', '', 'wrong-hash', '', self.digest]
        self.upload()
        self.assertEqual(sum(c.args[0] == 'push' for c in self.transport.call_args_list), 1)
        self.assertEqual(self.transport.call_args_list[-1].args[0], 'shell')

    def test_bad_legacy_transfer_aborts_before_partition_write(self):
        self.transport.side_effect = ['', '', '', 'wrong-hash', '', 'still-wrong']
        with self.assertRaisesRegex(SystemExit, 'no partition write performed'):
            self.upload()
        self.assertTrue(all('dd ' not in str(c) and 'reboot' not in str(c)
                            for c in self.transport.call_args_list))


if __name__ == '__main__':
    unittest.main()

# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('experiment_package', ROOT / 'scripts/g965n/package-experiments.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def overlay(missing_node=False):
    """Small real FDT fixture, independent of host dtc installation."""
    strings = bytearray()
    tokens = bytearray()

    def word(value):
        tokens.extend(struct.pack('>I', value))

    def begin(name):
        word(1)
        tokens.extend(name.encode() + b'\0')
        tokens.extend(b'\0' * (-len(tokens) % 4))

    def prop(name, value):
        offset = len(strings)
        strings.extend(name.encode() + b'\0')
        word(3); word(len(value)); word(offset)
        tokens.extend(value)
        tokens.extend(b'\0' * (-len(tokens) % 4))

    begin(''); begin('fragment@0'); prop('target-path', b'/\0'); begin('__overlay__')
    for name in ('mif_pdata', 'shmem@F6E00000', 'mcu_ipc@14170000'):
        if missing_node and name == 'shmem@F6E00000':
            continue
        begin(name)
        if name == 'mif_pdata':
            prop('samsung,hw-revision', struct.pack('>I', 26))
        word(2)
    word(2); word(2); word(2); word(9)
    start = 56
    total = start + len(tokens) + len(strings)
    header = struct.pack('>10I', 0xd00dfeed, total, start, start + len(tokens), 40, 17, 16, 0, len(strings), len(tokens))
    return header + bytes(16) + tokens + strings


class ExperimentPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'experimental'; self.output.mkdir()
        self.kernel = self.root / 'kernel'
        (self.kernel / 'include/generated').mkdir(parents=True)
        (self.kernel / 'include/config').mkdir()
        (self.kernel / 'include/generated/utsversion.h').write_text('#define UTS_VERSION "fixture"\n')
        (self.kernel / 'include/config/kernel.release').write_text('7.1.0\n')
        (self.kernel / '.config').write_text('CONFIG_CRYPTO_AES=y\n')
        self.boot = self.root / 'boot.img'; self.boot.write_bytes(b'ANDROID!fixture')

    def run_package(self, features, stock=None):
        for feature in features:
            path = self.output / feature / package.FILES[feature]
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'module fixture')
        args = ['package-experiments.py', '--kernel-out', str(self.kernel), '--boot', str(self.boot),
                '--output', str(self.output), '--source-commit', 'a' * 40, '--features', *features]
        if stock is not None:
            args += ['--stock-boot', str(stock)]
        with patch.object(sys, 'argv', args):
            package.main()
        return json.loads((self.output / 'manifest.json').read_text())

    def test_audio_bluetooth_receipt_remains_compatible_without_overlay(self):
        receipt = self.run_package(['audio', 'bluetooth'])
        self.assertNotIn('artifacts', receipt)
        self.assertEqual(set(receipt['modules']), {'audio', 'bluetooth'})

    def test_iio_bridge_requires_exact_core_and_records_module(self):
        with self.assertRaises(SystemExit):
            self.run_package(['iio-bridge'])
        self.assertFalse((self.output / 'manifest.json').exists())
        (self.kernel / '.config').write_text('CONFIG_IIO=y\n')
        receipt = self.run_package(['iio-bridge'])
        self.assertTrue(receipt['built_in_iio'])
        self.assertEqual(receipt['modules']['iio-bridge']['path'], 'iio-bridge/g965n-iio-bridge.ko')

    def test_modem_requires_the_actual_overlay_before_writing_receipt(self):
        with self.assertRaises(FileNotFoundError):
            self.run_package(['modem'])
        self.assertFalse((self.output / 'manifest.json').exists())

    def write_overlay(self, data=None):
        path = self.output / 'modem/modem.dtbo'; path.parent.mkdir(exist_ok=True)
        path.write_bytes(overlay() if data is None else data)
        return path

    def test_overlay_hash_source_and_unqualified_scope_are_recorded(self):
        path = self.write_overlay()
        item = self.run_package(['modem'])['artifacts']['modem_overlay']
        self.assertEqual(item['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(item['bytes'], path.stat().st_size)
        self.assertEqual(item['source']['license'], 'GPL-2.0-only')
        self.assertEqual(item['stock_verification']['status'], 'not-performed')
        self.assertEqual(item['firmware_request'], 'g965n/modem.dtbo')

    def test_missing_hardware_node_and_non_fdt_are_rejected(self):
        for data in (overlay(missing_node=True), bytes(64)):
            self.write_overlay(data)
            with self.assertRaises(ValueError):
                self.run_package(['modem'])

    def test_stock_verifier_failure_cannot_qualify_the_package(self):
        self.write_overlay()
        with patch.object(package.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'verify')):
            with self.assertRaises(subprocess.CalledProcessError):
                self.run_package(['modem'], self.boot)
        self.assertFalse((self.output / 'manifest.json').exists())

    def test_explicit_stock_comparison_is_checked_before_pass_receipt(self):
        self.write_overlay()
        with patch.object(package.subprocess, 'run') as run:
            item = self.run_package(['modem'], self.boot)['artifacts']['modem_overlay']
        self.assertEqual(item['stock_verification']['status'], 'passed')
        self.assertTrue(run.call_args.kwargs['check'])
        self.assertIn(str(self.boot), run.call_args.args[0])


if __name__ == '__main__':
    unittest.main()

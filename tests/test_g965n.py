# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts/g965n'
sys.path.insert(0, str(SCRIPTS))
from device import Device, PARTITIONS
from firmware import FILES, stage

DATA = b'partition backup\x00\xff'


class FakeDevice(Device):
    bootloader = 'G965NKSU5FVA2'
    state = 'recovery'
    corrupt = False

    def __init__(self):
        self.commands = []

    def call(self, *args, **kwargs):
        self.commands.append(args)
        if args[0] == 'get-state':
            return types.SimpleNamespace(stdout=self.state.encode())
        if args[0] == 'exec-out':
            if not args[1].endswith('2>/dev/null'):
                raise AssertionError('Remote dd stderr could corrupt binary stdout')
            kwargs['stdout'].write(DATA + (b'bad' if self.corrupt else b''))
            return types.SimpleNamespace(stdout=b'')
        raise AssertionError(args)

    def shell(self, command):
        values = {'getprop ro.bootloader': self.bootloader,
                  'getprop ro.product.device': 'star2lte',
                  'getprop ro.twrp.version': '3.3.1-0', 'id -u': '0'}
        if command in values:
            return values[command]
        if command.startswith('readlink -f '):
            return '/dev/block/' + PARTITIONS[command.rsplit('/', 1)[1]]
        if command.startswith('blockdev '):
            return str(len(DATA))
        if command.startswith('sha256sum '):
            return hashlib.sha256(DATA).hexdigest() + '  device'
        raise AssertionError(command)


class RecoveryTests(unittest.TestCase):
    def test_model_guard(self):
        d = FakeDevice()
        d.bootloader = 'G965FXX'
        with self.assertRaisesRegex(RuntimeError, 'SM-G965N'):
            d.inspect()

    def test_recovery_guard(self):
        d = FakeDevice()
        d.state = 'device'
        with self.assertRaisesRegex(RuntimeError, 'TWRP'):
            d.inspect()

    def test_backup_hash_size_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'backup'
            result = FakeDevice().backup(out)
            self.assertTrue(result['complete'])
            self.assertEqual(len(result['partitions']), 9)
            self.assertEqual((out / 'BOOT.img').read_bytes(), DATA)
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)

    def test_corrupt_stream_never_marked_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'backup'
            d = FakeDevice()
            d.corrupt = True
            with self.assertRaisesRegex(RuntimeError, 'byte count mismatch'):
                d.backup(out)
            self.assertFalse((out / 'manifest.json').exists())

    def test_installer_requires_explicit_erase_consent_before_adb(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'install.py'),
            '--adb', '/nonexistent/adb', '--serial', 'unused', '--backup', '/unused',
            '--boot', '/unused', '--rootfs', '/unused'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('consent', result.stderr)
        self.assertNotIn('FileNotFoundError', result.stderr)


class FirmwareTests(unittest.TestCase):
    def test_git_excludes_stock_filenames_including_nvram_suffix(self):
        root = SCRIPTS.parents[1]
        paths = ['firmware/' + name for name in FILES]
        paths += ['firmware/regulatory.db', 'firmware/regulatory.db.p7s',
                  'device/base/lib/firmware/brcm/brcmfmac4361-pcie.bin',
                  '.local/image.env', '.local/stock-firmware/bcmdhd_sta.bin_b2']
        for path in paths:
            result = subprocess.run(['git', 'check-ignore', '--no-index', '--quiet', path], cwd=root)
            self.assertEqual(result.returncode, 0, path)

    def test_original_bytes_preserved_and_conflicts_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = root / 'input'
            inputs.mkdir()
            for name in FILES:
                (inputs / name).write_bytes(b'local-own-firmware\r\n')
            stage(inputs, root)
            for name, mapped in FILES.items():
                expected = (inputs / name).read_bytes()
                if name.startswith('nvram'):
                    expected = expected.replace(b'\r\n', b'\n')
                self.assertEqual((root / 'device/base/lib/firmware/brcm' / mapped).read_bytes(),
                                 expected)
                self.assertEqual((root / 'firmware' / name).read_bytes(), (inputs / name).read_bytes())
            (inputs / next(iter(FILES))).write_bytes(b'different')
            with self.assertRaisesRegex(ValueError, 'Different firmware'):
                stage(inputs, root)


if __name__ == '__main__':
    unittest.main()

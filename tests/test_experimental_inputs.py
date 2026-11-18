# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/g965n'))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hub = load('hub_extract', 'experiments/sensors/extract-hub-patch.py')
installer = load('kernel_installer', 'scripts/g965n/install.py')


class HubInputTests(unittest.TestCase):
    record = b'<FormatVersion=0x00010003>\n<BlobLength=2>\n<Name=bcm_sensorhub_a1>\n<Blob=0011>\n'

    def test_exact_record_and_c_terminator(self):
        self.assertEqual(hub.extract(b'prefix' + self.record + b'\0suffix'), self.record + b'\0')

    def test_reject_ambiguous_missing_or_corrupt_patch(self):
        for data in (self.record, self.record + b'\0' + self.record + b'\0',
                     self.record.replace(b'Length=2', b'Length=3') + b'\0'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                hub.extract(data)


class KernelUpdateTests(unittest.TestCase):
    def test_kernel_only_never_delegates_userdata_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            backup = root / 'backup'; backup.mkdir()
            dist = root / 'dist'; dist.mkdir()
            boot = dist / 'boot.img'; boot.write_bytes(b'ANDROID!test')
            entries = []
            for name in installer.PARTITIONS:
                file = backup / (name + '.img'); file.write_bytes(b'private fixture')
                entries.append({'name': name, 'bytes': file.stat().st_size, 'sha256': installer.digest(file)})
            (backup / 'manifest.json').write_text(json.dumps({
                'complete': True, 'bootloader': 'G965N-test', 'partitions': entries}))
            device = MagicMock()
            device.inspect.return_value = {'bootloader': 'G965N-test'}
            device.shell.return_value = entries[0]['sha256'] + ' partition'
            args = ['install.py', '--serial', 'fixture', '--backup', str(backup),
                    '--boot', str(boot), '--update-kernel-experimental-g965n']
            with patch.object(installer, 'ROOT', root), patch.object(installer, 'Device', return_value=device), \
                 patch.object(sys, 'argv', args), patch.object(installer.subprocess, 'run') as run:
                installer.main()
            self.assertEqual(run.call_count, 1)
            self.assertEqual(Path(run.call_args.args[0][1]).name, 'flash_s9plus_boot_adb.py')


if __name__ == '__main__':
    unittest.main()

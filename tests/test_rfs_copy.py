# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import importlib.util
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / 'experiments/modem/rfs-copy.py'
spec = importlib.util.spec_from_file_location('rfs_copy_test', path)
rfs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rfs)


class PrivateNVTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        original = base / 'original'; original.mkdir()
        self.original = original / 'nv_data.bin'
        self.original.write_bytes(bytes(range(256)) * 4)
        (original / 'nv_data.bin.md5').write_text(hashlib.md5(self.original.read_bytes() + rfs.SALT).hexdigest())
        self.working = base / 'working'; shutil.copytree(original, self.working)

    def test_write_and_read_only_working_copy_with_valid_checksum(self):
        nv = rfs.WorkingNV(self.working); self.addCleanup(nv.close)
        original = self.original.read_bytes()
        request = struct.pack('<IBBII', 18, 2, 9, 12, 4) + b'test'
        response = nv.handle(request)
        self.assertEqual(struct.unpack('<IBBBII', response), (15, 2, 9, 1, 12, 4))
        self.assertEqual(self.original.read_bytes(), original)
        self.assertEqual((self.working / 'nv_data.bin').read_bytes()[12:16], b'test')
        self.assertEqual(nv.digest(), (self.working / 'nv_data.bin.md5').read_text())
        response = nv.handle(struct.pack('<IBBII', 14, 1, 10, 12, 4))
        self.assertEqual(response[15:], b'test')

    def test_out_of_bounds_and_remote_paths_never_modify_or_open_host_files(self):
        nv = rfs.WorkingNV(self.working); self.addCleanup(nv.close)
        before = nv.digest()
        response = nv.handle(struct.pack('<IBBII', 18, 2, 3, 1023, 4) + b'bad!')
        self.assertEqual(response[6], 0)
        self.assertEqual(nv.digest(), before)
        remote = b'../../dev/sda3\0'
        response = nv.handle(struct.pack('<IBB', len(remote) + 6, 0x11, 4) + remote)
        self.assertEqual(struct.unpack_from('<i', response, 6)[0], -1)
        self.assertEqual(nv.digest(), before)

    def test_reject_invalid_checksum_and_symlink(self):
        (self.working / 'nv_data.bin.md5').write_text('0' * 32)
        with self.assertRaises(ValueError):
            rfs.WorkingNV(self.working)
        (self.working / 'nv_data.bin').unlink()
        (self.working / 'nv_data.bin').symlink_to(self.original)
        with self.assertRaises(OSError):
            rfs.WorkingNV(self.working)


if __name__ == '__main__':
    unittest.main()

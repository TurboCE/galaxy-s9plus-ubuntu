# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rfs_capture',ROOT/'experiments/modem/rfs-copy.py')
rfs=importlib.util.module_from_spec(spec);spec.loader.exec_module(rfs)


def frame(command,body):
    return struct.pack('<IBB',len(body)+6,command,1)+body


class PrivateCaptureTests(unittest.TestCase):
    def test_only_open_close_are_recorded_and_existing_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();directory.chmod(0o700);path=directory/'capture'
            capture=rfs.PrivateOpenCapture(path)
            try:
                capture.record(frame(2,b'synthetic NV payload must never be recorded'))
                self.assertEqual(path.stat().st_size,0)
                opened=frame(0x11,b'synthetic/file\0')
                capture.record(opened)
                self.assertEqual(path.read_bytes(),struct.pack('<I',len(opened))+opened)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
                with self.assertRaises(FileExistsError):rfs.PrivateOpenCapture(path)
                link=directory/'link';link.symlink_to(path)
                with self.assertRaises(OSError):rfs.PrivateOpenCapture(link)
            finally:capture.close()

    def test_permissions_format_and_count_bounds(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name).resolve();directory.chmod(0o755)
            with self.assertRaisesRegex(ValueError,'private'):rfs.PrivateOpenCapture(directory/'capture')
            directory.chmod(0o700);capture=rfs.PrivateOpenCapture(directory/'capture')
            try:
                with self.assertRaises(ValueError):capture.record(b'bad')
                with self.assertRaises(ValueError):capture.record(frame(0x11,b'x'*65536))
                for _ in range(128):capture.record(frame(6,b'\0'*4))
                with self.assertRaisesRegex(ValueError,'bound'):capture.record(frame(6,b'\0'*4))
            finally:capture.close()


if __name__=='__main__':unittest.main()

# SPDX-License-Identifier: GPL-2.0-only
"""Private namespace isolation and measured modern-RFS wire contracts."""
import errno
import importlib.util
import os
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('rfs_diagnostic_test',
    Path(__file__).resolve().parents[1]/'experiments/modem/rfs-copy.py')
rfs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rfs)


def frame(command, payload=b'', ident=7):
    return struct.pack('<IBB', 6+len(payload), command, ident)+payload


def opened(broker, name=b'err/csdiag_mmrj_Info.dat', flags=66):
    name += b'\0'
    return broker.handle(frame(17, struct.pack('<II', flags, len(name))+name))


def result(response):
    return struct.unpack_from('<ii', response, 6)


class DiagnosticFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve(); self.directory.chmod(0o700)
        self.broker = rfs.PrivateDiagnosticFiles(self.directory); self.addCleanup(self.broker.close)

    def test_create_write_seek_read_close_and_reopen(self):
        response = opened(self.broker)
        self.assertEqual(struct.unpack('<IBBii', response), (14,17,7,1,0))
        handle = result(response)[0]
        self.assertEqual(result(self.broker.handle(frame(4,struct.pack('<iI',handle,4)+b'test'))), (4,0))
        response = self.broker.handle(frame(5,struct.pack('<iII',handle,0,0)))
        self.assertEqual(struct.unpack('<IBBiii',response),(18,5,7,0,0,0))
        response = self.broker.handle(frame(3,struct.pack('<iI',handle,10)))
        self.assertEqual(struct.unpack('<IBBii',response[:14]),(18,3,7,4,0))
        self.assertEqual(response[14:],b'test')
        self.assertEqual(result(self.broker.handle(frame(3,struct.pack('<iI',handle,10)))),(0,0))
        self.assertEqual(result(self.broker.handle(frame(6,struct.pack('<i',handle)))),(0,0))
        self.assertEqual(result(self.broker.handle(frame(6,struct.pack('<i',handle)))),(-1,errno.EBADF))
        other = result(opened(self.broker,flags=0))[0]
        self.assertEqual(result(self.broker.handle(frame(4,struct.pack('<iI',other,1)+b'x'))),(-1,errno.EBADF))
        path=self.directory/'network-diagnostic.bin'
        self.assertEqual(path.read_bytes(),b'test');self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_only_exact_diagnostic_names_and_reviewed_flags(self):
        for name in (b'../nv_data.bin',b'/efs/nv_data.bin',b'CP_AUDIO_SLSI.bin',
                     b'err/../csdiag_mmrj_Info.dat',b'err/csdiag_mmrj_Info.dat/x'):
            self.assertEqual(result(opened(self.broker,name)),(-1,errno.ENOENT))
        self.assertEqual(list(self.directory.iterdir()),[])
        for flags in (1,2,64,512,1024,0xffffffff):
            self.assertEqual(result(opened(self.broker,flags=flags)),(-1,errno.EINVAL))
        self.assertEqual(result(opened(self.broker,flags=0)),(-1,errno.ENOENT))
        self.assertEqual(result(opened(self.broker,b'err/csdiag_rf_Mipi.dat')),(1,0))

    def test_bad_frames_do_not_create_or_write(self):
        for request in (b'',frame(17,b'\0'*8),frame(17,struct.pack('<II',66,2)+b'x\0z'),
                        frame(17,struct.pack('<II',66,4)+b'a\0b\0'),frame(4,struct.pack('<iI',1,2)+b'x'),
                        frame(3,struct.pack('<iI',1,65537)),frame(6,struct.pack('<ii',1,0)),
                        frame(5,struct.pack('<ii',1,0)),frame(99)):
            with self.assertRaises(ValueError):self.broker.handle(request)
        self.assertEqual(list(self.directory.iterdir()),[])

    def test_bounds_and_virtual_handles(self):
        # Host descriptors are never accepted in place of exported handles.
        self.assertEqual(result(self.broker.handle(frame(4,struct.pack('<iI',100000,1)+b'x'))),(-1,errno.EBADF))
        h=result(opened(self.broker))[0]
        self.assertEqual(result(self.broker.handle(frame(5,struct.pack('<iII',h,262144,0))))[1],262144)
        self.assertEqual(result(self.broker.handle(frame(4,struct.pack('<iI',h,1)+b'x'))),(-1,errno.EFBIG))
        self.assertEqual(struct.unpack_from('<iii',self.broker.handle(frame(5,struct.pack('<iII',h,1,1))),6)[2],errno.EFBIG)
        self.assertEqual(struct.unpack_from('<iii',self.broker.handle(frame(5,struct.pack('<iII',h,0,99))),6)[2],errno.EINVAL)
        for _ in range(7):self.assertGreater(result(opened(self.broker))[0],0)
        self.assertEqual(result(opened(self.broker)),(-1,errno.EMFILE))
        self.broker.operations=4096
        with self.assertRaisesRegex(ValueError,'bound'):opened(self.broker)

    def test_existing_or_linked_namespace_is_refused(self):
        # A later run must use a fresh directory, preserving all prior evidence.
        opened(self.broker)
        with self.assertRaisesRegex(ValueError,'empty'):rfs.PrivateDiagnosticFiles(self.directory)
        self.directory.chmod(0o755)
        with self.assertRaisesRegex(ValueError,'private'):rfs.PrivateDiagnosticFiles(self.directory)
        self.directory.chmod(0o700)
        with tempfile.TemporaryDirectory() as parent:
            link=Path(parent)/'link';link.symlink_to(self.directory)
            with self.assertRaises(ValueError):rfs.PrivateDiagnosticFiles(link)


if __name__ == '__main__':unittest.main()

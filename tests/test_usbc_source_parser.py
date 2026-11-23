# SPDX-License-Identifier: GPL-2.0-only
"""Compile the actual parser and check synthetic wire replies, including truncation."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PDO(ctypes.Structure):
    _fields_ = [(k, ctypes.c_uint) for k in ('index', 'current_ua', 'voltage_uv')]

class SourceParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('cc')
        if not cc:
            raise unittest.SkipTest('Host C compiler unavailable')
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        (root/'test.c').write_text('#include "s9p-max77705-source.h"\n'
            'bool parse(const unsigned char *b,size_t n,struct s9p_source_pdo *p) {'
            'return s9p_source_pdo_parse(b,n,p);}\n')
        output = root/'parser.so'
        subprocess.run([cc, '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
            '-I'+str(ROOT/'src/soc'), str(root/'test.c'), '-o', str(output)], check=True)
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(PDO)]
        cls.lib.parse.restype = ctypes.c_bool

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def parse(self, frame):
        result = PDO(99, 99, 99)
        valid = self.lib.parse(bytes(frame), len(frame), ctypes.byref(result))
        return valid, (result.index, result.current_ua, result.voltage_uv)

    def test_selected_fixed_pdo_and_units(self):
        pdo5v3a = ((5000//50) << 10) | (3000//10)
        pdo9v2a = ((9000//50) << 10) | (2000//10)
        frame = bytes([0x30, (2<<3)|2]) + pdo5v3a.to_bytes(4,'little') + pdo9v2a.to_bytes(4,'little')
        self.assertEqual(self.parse(frame), (True, (2,2000000,9000000)))
        for length in range(len(frame)):
            self.assertEqual(self.parse(frame[:length]), (False, (99,99,99)))

    def test_no_pdo_wrong_opcode_bad_index_zero_and_nonfixed(self):
        valid = ((5000//50)<<10) | 300
        for opcode, summary, pdo in ((0x06,9,valid),(0x30,0,valid),
                (0x30,17,valid),(0x30,9,0),(0x30,9,300),
                (0x30,9,100<<10),(0x30,9,valid|(1<<30)),
                (0x30,9,valid|(2<<30)),(0x30,9,valid|(3<<30))):
            frame = bytes([opcode,summary]) + pdo.to_bytes(4,'little')
            self.assertEqual(self.parse(frame), (False, (99,99,99)))

    def test_seventh_pdo_bounds(self):
        pdo = ((5000//50)<<10) | 150
        frame = bytes([0x30,63]) + pdo.to_bytes(4,'little')*7
        self.assertEqual(self.parse(frame), (True,(7,1500000,5000000)))

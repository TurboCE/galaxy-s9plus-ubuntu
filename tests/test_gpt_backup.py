# SPDX-License-Identifier: GPL-2.0-only
"""Exercise GPT metadata derivation and refusals with synthetic, private-free data."""
import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

SPEC = importlib.util.spec_from_file_location('gpt_backup', Path(__file__).resolve().parents[1] / 'experiments/storage/gpt-backup.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecondaryGPT(unittest.TestCase):
    def setUp(self):
        self.sector, self.size = 4096, 4096 * 4096
        table = bytearray(128 * 128)
        table[:16] = bytes([1]) * 16
        struct.pack_into('<2Q', table, 32, 6, 4000)
        header = bytearray(4096)
        header[:8] = b'EFI PART'
        struct.pack_into('<4I', header, 8, 0x10000, 92, 0, 0)
        struct.pack_into('<4Q', header, 24, 1, 4095, 6, 4090)
        struct.pack_into('<QIII', header, 72, 2, 128, 128, zlib.crc32(table))
        struct.pack_into('<I', header, 16, zlib.crc32(header[:92]))
        self.primary = bytes(4096) + header + table
        self.tail = bytes(6 * 4096)

    def test_secondary_reverses_header_locations_and_keeps_table(self):
        original = bytes(self.primary)
        offset, data, count = MODULE.plan(self.primary, self.tail, self.sector, self.size)
        self.assertEqual(offset, 4091 * 4096)
        self.assertEqual(len(data), 5 * 4096)
        self.assertEqual(count, 1)
        self.assertEqual(data[:4 * 4096], self.primary[2 * 4096:])
        header = bytearray(data[-4096:])
        self.assertEqual(struct.unpack_from('<2Q', header, 24), (4095, 1))
        self.assertEqual(struct.unpack_from('<Q', header, 72)[0], 4091)
        crc = struct.unpack_from('<I', header, 16)[0]
        struct.pack_into('<I', header, 16, 0)
        self.assertEqual(crc, zlib.crc32(header[:92]))
        self.assertEqual(self.primary, original)

    def test_refuses_existing_or_nonzero_backup_region(self):
        for offset in (-1, -4096, -5 * 4096):
            tail = bytearray(self.tail)
            tail[offset] = 1
            with self.assertRaisesRegex(RuntimeError, 'not empty'):
                MODULE.plan(self.primary, tail, self.sector, self.size)

    def test_samsung_512_byte_header_preserves_length_and_full_crc(self):
        primary = bytearray(self.primary)
        struct.pack_into('<I', primary, 4096 + 12, 512)
        struct.pack_into('<I', primary, 4096 + 16, 0)
        struct.pack_into('<I', primary, 4096 + 16, zlib.crc32(primary[4096:4096 + 512]))
        _, data, _ = MODULE.plan(primary, self.tail, self.sector, self.size)
        header = bytearray(data[-4096:])
        self.assertEqual(struct.unpack_from('<I', header, 12)[0], 512)
        crc = struct.unpack_from('<I', header, 16)[0]
        struct.pack_into('<I', header, 16, 0)
        self.assertEqual(crc, zlib.crc32(header[:512]))

    def test_refuses_bad_header_or_array_crc(self):
        for offset in (4096 + 32, 8192 + 100):
            primary = bytearray(self.primary)
            primary[offset] ^= 1
            with self.assertRaisesRegex(RuntimeError, 'CRC mismatch'):
                MODULE.plan(primary, self.tail, self.sector, self.size)

    def test_refuses_partition_outside_usable_range_even_with_valid_crc(self):
        primary = bytearray(self.primary)
        struct.pack_into('<Q', primary, 8192 + 40, 4095)
        struct.pack_into('<I', primary, 4096 + 88, zlib.crc32(primary[8192:]))
        struct.pack_into('<I', primary, 4096 + 16, 0)
        struct.pack_into('<I', primary, 4096 + 16, zlib.crc32(primary[4096:4096 + 92]))
        with self.assertRaisesRegex(RuntimeError, 'outside usable'):
            MODULE.plan(primary, self.tail, self.sector, self.size)


if __name__ == '__main__':
    unittest.main()

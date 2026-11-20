# SPDX-License-Identifier: GPL-2.0-only
"""Validate real fix classification and coordinate-free summaries."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    'gnss_check', Path(__file__).resolve().parents[1] / 'experiments/gnss/check-fix.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def frame(body):
    checksum = 0
    for byte in body.encode('ascii'):
        checksum ^= byte
    return f'${body}*{checksum:02X}\r\n'.encode('ascii')


class FixCheck(unittest.TestCase):
    def collect(self, raw):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / 'summary.json'
            reader, writer = socket.socketpair()
            with reader, writer:
                writer.sendall(raw)
                writer.shutdown(socket.SHUT_WR)
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    result = CHECK.collect(reader, 15, summary)
            state = json.loads(summary.read_text())
            self.assertTrue(state['final'])
            self.assertNotIn('$GP', output.getvalue())
            self.assertNotIn('1200.000', output.getvalue())
            self.assertNotIn('latitude', state)
            self.assertNotIn('longitude', state)
            return result, state

    def test_no_fix_despite_valid_nmea(self):
        result, state = self.collect(frame('GPGGA,000000,,,,,0,0,,,,,,,') +
                                     frame('GPGSA,A,1,,,,,,,,,,,,,99,99,99'))
        self.assertFalse(result)
        self.assertEqual(state['valid_sentences'], 2)
        self.assertEqual(state['gsa_fix_type_max'], 1)

    def test_gga_fix_and_satellites(self):
        result, state = self.collect(frame('GPGGA,000000,1200.000,N,02400.000,E,1,8,1,0,M,0,M,,') +
                                     frame('GPGSV,1,1,8'))
        self.assertTrue(result)
        self.assertEqual(state['satellites_used_max'], 8)
        self.assertEqual(state['satellites_in_view_max'], 8)

    def test_rmc_fix(self):
        result, _ = self.collect(frame('GPRMC,000000,A,1200.000,N,02400.000,E,0,0,010100,,,A'))
        self.assertTrue(result)

    def test_bad_checksum_does_not_qualify(self):
        result, state = self.collect(b'$GPRMC,000000,A,1200.000,N,02400.000,E*XX\r\n')
        self.assertFalse(result)
        self.assertEqual(state['invalid_sentences'], 1)

    def test_missing_or_invalid_coordinates_do_not_qualify(self):
        result, _ = self.collect(frame('GPGGA,000000,,,,,1,8,1,0,M,0,M,,') +
                                 frame('GPRMC,000000,A,8999.000,N,02400.000,E,0,0,010100,,,A'))
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()

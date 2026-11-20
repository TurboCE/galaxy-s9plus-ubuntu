# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'gnss_assistance', Path(__file__).resolve().parents[1] / 'experiments/gnss/assistance.py')
AID = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AID)


class Assistance(unittest.TestCase):
    def setUp(self):
        self.config = b'XTRA_SERVER_1=http://gllto1.glpals.com/4day/v5/latest/lto2.dat\n'
        self.data = b'test-only-not-receiver-data' * 40
        self.now = 2_000_000_000
        self.meta = {'source': AID.sources(self.config)[0], 'downloaded_at': self.now,
                     'modified_at': self.now - 3600,
                     'config_sha256': hashlib.sha256(self.config).hexdigest(),
                     'sha256': hashlib.sha256(self.data).hexdigest()}

    def test_only_configured_v5_source_upgrades_to_https(self):
        self.assertEqual(AID.sources(self.config),
                         ['https://gllto1.glpals.com/4day/v5/latest/lto2.dat'])
        for url in [b'http://example.com/4day/v5/latest/lto2.dat',
                    b'https://gllto1.glpals.com/4day/v4/latest/lto2.dat',
                    b'https://gllto1.glpals.com/4day/v5/latest/lto2.dat?token=secret']:
            with self.assertRaises(RuntimeError):
                AID.sources(b'XTRA_SERVER_1=' + url)

    def test_fresh_integrity_checked_metadata(self):
        self.assertTrue(AID.valid_metadata(self.meta, self.data, self.config, self.now))

    def test_expired_or_future_cache_rejected(self):
        for key, value in [('downloaded_at', self.now - AID.TTL),
                           ('modified_at', self.now - AID.VALIDITY),
                           ('modified_at', self.now + 1)]:
            self.assertFalse(AID.valid_metadata(dict(self.meta, **{key: value}),
                                               self.data, self.config, self.now))

    def test_tampered_blob_config_and_unconfigured_source_rejected(self):
        self.assertFalse(AID.valid_metadata(self.meta, self.data + b'x', self.config, self.now))
        self.assertFalse(AID.valid_metadata(self.meta, self.data, self.config + b'changed', self.now))
        self.assertFalse(AID.valid_metadata(dict(self.meta, source='https://example.com/data'),
                                           self.data, self.config, self.now))
        self.assertFalse(AID.valid_metadata([], self.data, self.config, self.now))


if __name__ == '__main__':
    unittest.main()

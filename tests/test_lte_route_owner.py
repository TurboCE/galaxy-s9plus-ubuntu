# SPDX-License-Identifier: GPL-2.0-only
"""The route owner accepts only a short, validated bearer lease."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lte_route_owner', ROOT / 'scripts/g965n/lte-route-owner.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


class RouteLeaseTests(unittest.TestCase):
    def test_expired_missing_and_invalid_leases_do_not_grant_routing(self):
        config = {'cid': 1, 'ipv4': '192.0.2.2', 'dns4': ['192.0.2.53'], 'mtu': 1450}
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'lease.json'
            self.assertIsNone(owner.read_lease(path, 100))
            original_fstat = os.fstat

            def root_fixture(fd):
                st = original_fstat(fd)
                return SimpleNamespace(st_uid=0, st_mode=st.st_mode, st_nlink=st.st_nlink)

            with patch.object(owner.os, 'fstat', side_effect=root_fixture):
                def read(expiry, candidate=config):
                    path.write_text(json.dumps({'generation': 2, 'valid_until': expiry, 'config': candidate}))
                    path.chmod(0o600)
                    return owner.read_lease(path, 100)

                self.assertIsNone(read(100))
                self.assertEqual(read(105.1), (2, '192.0.2.2', ('192.0.2.53',), 1450))
                for expiry, candidate in ((107, config), (105, config | {'dns4': ['127.0.0.1']}),
                                          (105, config | {'cid': 2})):
                    with self.assertRaises(RuntimeError):
                        read(expiry, candidate)


if __name__ == '__main__':
    unittest.main()

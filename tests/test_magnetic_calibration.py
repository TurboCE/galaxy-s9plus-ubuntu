# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('magnetic_input',ROOT/'experiments/sensors/prepare-magnetic-calibration.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class MagneticInputTests(unittest.TestCase):
    def test_backup_model_checksum_size_and_ordinary_file_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);p=root/'EFS.img';p.write_bytes(b'fixture')
            base={'complete':True,'model':'SM-G965N','bootloader':'G965N-fixture',
                  'partitions':[{'name':'EFS','bytes':7,'sha256':hashlib.sha256(b'fixture').hexdigest()}]}
            manifest=root/'manifest.json'
            manifest.write_text(json.dumps(base))
            self.assertEqual(m.verified_backup(p,'EFS'),(p,base['partitions'][0]['sha256']))
            for changes in ({'complete':False},{'model':'SM-G955N'},
                            {'bootloader':'G965F-fixture'},
                            {'partitions':[]},{'partitions':base['partitions']*2},
                            {'partitions':[{**base['partitions'][0],'bytes':8}]},
                            {'partitions':[{**base['partitions'][0],'sha256':'0'*64}]}):
                manifest.write_text(json.dumps({**base,**changes}))
                with self.assertRaises(ValueError):m.verified_backup(p,'EFS')
            manifest.write_text(json.dumps(base));p.unlink();p.symlink_to(root/'target')
            with self.assertRaises(ValueError):m.verified_backup(p,'EFS')

if __name__=='__main__':unittest.main()

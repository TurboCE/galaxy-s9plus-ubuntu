# SPDX-License-Identifier: GPL-2.0-only
"""Verify bounded private diagnostic retention and incomplete sensor records."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('observer',ROOT/'experiments/charging/charge-observer.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ObserverTests(unittest.TestCase):
    def test_rotation_retains_latest_records_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'state';j=m.Journal(root,limit=60)
            for i in range(50):j.append({'sequence':i,'data':'x'*20})
            files=list(root.glob('*.jsonl'))
            self.assertEqual(len(files),4)
            self.assertEqual(json.loads((root/'samples.jsonl').read_text())['sequence'],49)
            for p in files:
                self.assertLessEqual(p.stat().st_size,60)
                self.assertEqual(p.stat().st_mode&0o077,0)
            with self.assertRaises(ValueError):j.append({'huge':'x'*100})

    def test_public_state_directory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'state';root.mkdir(mode=0o755)
            with self.assertRaises(RuntimeError):m.Journal(root)

    def test_symlink_target_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'state';j=m.Journal(root)
            target=Path(tmp)/'protected';target.write_text('untouched')
            (root/'samples.jsonl').symlink_to(target)
            with self.assertRaises(OSError):j.append({'data':1})
            self.assertEqual(target.read_text(),'untouched')


class StartupPowerTests(unittest.TestCase):
    def test_transient_voltage_dip_waits_for_two_consecutive_good_samples(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'capacity').write_text('20');(root/'voltage_now').write_text('3400000')
            values=iter(('3600000','3400000','3600000','3600000'));tick=[0]
            def sleep(seconds):
                tick[0]+=seconds;(root/'voltage_now').write_text(next(values))
            m.wait_stable_battery(root,clock=lambda:tick[0],sleep=sleep)
            self.assertEqual(tick[0],8)

    def test_persistent_low_voltage_never_proceeds(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'capacity').write_text('20');(root/'voltage_now').write_text('3400000');tick=[0]
            def sleep(seconds):tick[0]+=seconds
            with self.assertRaises(RuntimeError):m.wait_stable_battery(root,clock=lambda:tick[0],sleep=sleep)
            self.assertEqual(tick[0],30)

if __name__=='__main__':unittest.main()

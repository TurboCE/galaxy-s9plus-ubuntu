# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2p_trial',ROOT/'scripts/g965n/p2p-control-trial.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class P2pControlTrialTests(unittest.TestCase):
    def test_non_netdev_inventory_keeps_primary_and_created_context_distinct(self):
        text='''phy#0
 Interface wlp1s0
  ifindex 2
  wdev 0x1
  addr 00:00:00:00:00:01
  type managed
 Unnamed/non-netdev interface
  wdev 0xA
  addr 00:00:00:00:00:02
  type P2P-device
'''
        inventory=p.devices(text)
        self.assertEqual(set(inventory),{'0x1','0xa'})
        self.assertEqual(inventory['0x1']['type'],'managed')
        self.assertEqual(inventory['0xa']['type'],'P2P-device')
        self.assertNotIn('addr',inventory['0xa'])

    def test_readonly_observer_opt_in_does_not_relax_trial_baseline(self):
        data=b'ANDROID!'+b'x'*24
        receipt={'model':'SM-G965N','kernel_release':'test','kernel_version':'exact','boot_bytes':32,'boot_sha256':hashlib.sha256(data).hexdigest()}
        backup={'model':'SM-G965N','complete':True,'bootloader':'G965Ntest','partitions':[{'name':n} for n in ['BOOT','DTB','DTBO','EFS','CPEFS','RADIO','MISC','RECOVERY','PARAM']]}
        with patch.object(p.Path,'read_bytes',return_value=b'samsung,star2lte\0'),patch.object(p.Path,'read_text',return_value='Y'),patch.object(p.os,'uname',return_value=SimpleNamespace(release='test',version='exact')),patch('builtins.open',side_effect=lambda *a,**kw:io.BytesIO(data)):
            with self.assertRaisesRegex(ValueError,'opt-in-off'):p.validate(receipt,backup)
            p.validate(receipt,backup,require_off=False)

    def test_wrong_model_backup_kernel_and_bounds_refuse_before_boot_read(self):
        receipt={'model':'SM-G965N','kernel_release':'test','kernel_version':'exact','boot_bytes':32}
        backup={'model':'SM-G965N','complete':True,'bootloader':'G965Ntest','partitions':[{'name':n} for n in ['BOOT','DTB','DTBO','EFS','CPEFS','RADIO','MISC','RECOVERY','PARAM']]}
        with patch.object(p.Path,'read_bytes',return_value=b'samsung,star2lte\0'),patch.object(p.os,'uname',return_value=SimpleNamespace(release='test',version='exact')),patch('builtins.open') as block:
            for changes in [{'model':'SM-G955N'},{'kernel_version':'wrong'},{'boot_bytes':57671681},{'boot_bytes':True}]:
                with self.assertRaises(ValueError):p.validate({**receipt,**changes},backup)
            with self.assertRaises(ValueError):p.validate(receipt,{**backup,'complete':False})
            with self.assertRaises(ValueError):p.validate(receipt,{**backup,'partitions':backup['partitions'][:-1]})
            block.assert_not_called()

if __name__=='__main__':unittest.main()

# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2p_trial',ROOT/'scripts/g965n/p2p-control-trial.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
observer_spec = importlib.util.spec_from_file_location(
    'p2p_observer', ROOT/'scripts/g965n/p2p-peer-observe.py'
)
observer = importlib.util.module_from_spec(observer_spec)
observer_spec.loader.exec_module(observer)

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

    def test_discovery_stop_failure_is_logged_and_reported_to_the_caller(self):
        repo = ModuleType('gi.repository')
        failure = RuntimeError('StopFind failed')
        bus = Mock()
        bus.call_sync.side_effect = [Mock(unpack=lambda: ([],)), None, failure]
        repo.Gio = SimpleNamespace(
            bus_get_sync=Mock(return_value=bus), BusType=SimpleNamespace(SYSTEM=0),
            DBusCallFlags=SimpleNamespace(NONE=0),
        )
        repo.GLib = SimpleNamespace(Variant=lambda signature, value: value)
        guard = SimpleNamespace(validate=Mock(), trusted_json=Mock(),
                                PARAM=Mock(), protected_parent=Mock())
        guard.PARAM.read_text.return_value = 'Y'
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=Mock()))
        with TemporaryDirectory() as directory:
            path = Path(directory)/'scan.json'
            args = ['observe', '--model', 'SM-G965N', '--receipt', '/receipt',
                    '--receipt-sha256', 'fake', '--backup', '/backup',
                    '--backup-sha256', 'fake', '--log', str(path), '--duration', '5',
                    '--confirm-backup-verified', '--consent-peer-find']
            with (patch.object(observer.os, 'geteuid', return_value=0),
                  patch.object(observer.importlib.util, 'spec_from_file_location', return_value=fake_spec),
                  patch.object(observer.importlib.util, 'module_from_spec', return_value=guard),
                  patch.object(observer.subprocess, 'check_output', return_value='/org/freedesktop/NetworkManager/Devices/1'),
                  patch.dict(sys.modules, {'gi': ModuleType('gi'), 'gi.repository': repo}),
                  patch.object(observer.time, 'monotonic', side_effect=[0, 6]),
                  patch.object(sys, 'argv', args),
                  patch('builtins.print') as output):
                with self.assertRaisesRegex(RuntimeError, 'StopFind failed'):
                    observer.main()
            self.assertEqual(json.loads(path.read_text())['error'], 'RuntimeError')
            self.assertEqual(json.loads(output.call_args.args[0])['error'], 'RuntimeError')
            self.assertEqual([call.args[3] for call in bus.call_sync.call_args_list],
                             ['Get', 'StartFind', 'StopFind'])

if __name__=='__main__':unittest.main()

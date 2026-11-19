# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('profile_rollback',ROOT/'scripts/g965n/sensor-profile-rollback.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

class ProfileRollbackTests(unittest.TestCase):
 def value(self,strict=False):
  profile=json.dumps({'model':'SM-G965N','expected_boot_sha256':'a'*64,'transport':{'strict_tx_ack':strict}}).encode()
  sha=hashlib.sha256(profile).hexdigest()
  unit=('ExecStart=/usr/bin/python3 /root/supervisor run --profile '+str(r.PROFILE)+' --profile-sha256 '+sha+' --model SM-G965N\n').encode()
  value={'schema':1,'model':'SM-G965N','boot_sha256':'a'*64,'boot_bytes':32,'kernel_version':'fixture','profile':{'kind':'profile'},'unit':{'kind':'unit'}}
  return value,{'profile':profile,'unit':unit}
 def test_checksum_or_enabled_baseline_rejected(self):
  with patch.object(r,'trusted',return_value=b'changed'):
   with self.assertRaises(ValueError):r.pinned({'path':'/root/test','sha256':'0'*64,'bytes':7})
  v,data=self.value(True)
  with patch.object(r,'pinned',side_effect=lambda e:data[e['kind']]):
   with self.assertRaisesRegex(ValueError,'disable'):r.baseline(v)
  v,data=self.value();data['unit']=data['unit'].replace(b'--profile-sha256 ',b'--wrong-sha256 ')
  with patch.object(r,'pinned',side_effect=lambda e:data[e['kind']]):
   with self.assertRaisesRegex(ValueError,'pin'):r.baseline(v)
 def test_wrong_boot_cannot_stop_service_or_write(self):
  v,data=self.value()
  with patch.object(r,'pinned',side_effect=lambda e:data[e['kind']]),patch.object(r,'verify_boot',side_effect=ValueError('wrong BOOT')),patch.object(r.subprocess,'run') as call,patch.object(r,'atomic_write') as write:
   with self.assertRaises(ValueError):r.restore(v,True)
   call.assert_not_called();write.assert_not_called()
 def test_actual_atomic_restore_and_explicit_reboot(self):
  with tempfile.TemporaryDirectory() as temporary:
   path=Path(temporary)
   with patch.object(r,'PROFILE',path/'profile.json'),patch.object(r,'UNIT',path/'sensor.service'):
    v,data=self.value()
    with patch.object(r,'pinned',side_effect=lambda e:data[e['kind']]),patch.object(r,'verify_boot'),patch.object(r.subprocess,'run') as call:
     r.restore(v,True)
    self.assertEqual(r.PROFILE.read_bytes(),data['profile'])
    self.assertEqual(r.UNIT.read_bytes(),data['unit'])
    self.assertEqual(stat.S_IMODE(r.PROFILE.stat().st_mode),0o600)
    self.assertEqual(stat.S_IMODE(r.UNIT.stat().st_mode),0o644)
    self.assertEqual(call.call_args_list[-1].args[0],['systemctl','reboot'])
    self.assertFalse(list(path.glob('.g965n-rollback-*')))
 def test_stop_failure_requires_explicit_reboot_before_staging_anything(self):
  v,data=self.value()
  with patch.object(r,'pinned',side_effect=lambda e:data[e['kind']]),patch.object(r,'verify_boot'),patch.object(r.subprocess,'run',side_effect=subprocess.TimeoutExpired('stop',220)),patch.object(r,'atomic_write') as write:
   with self.assertRaises(subprocess.TimeoutExpired):r.restore(v,False)
   write.assert_not_called()

if __name__=='__main__':unittest.main()

# SPDX-License-Identifier: GPL-2.0-only
import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('recovery',Path(__file__).resolve().parents[1]/'experiments/thermal/recovery-check.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class RecoveryTests(unittest.TestCase):
 def test_charge_permission_can_follow_cold_sample(self):
  p=m.observe_phases((False,False,False),405,0,True,['swelling_temperature_stop']);self.assertEqual(p,(True,False,False))
  p=m.observe_phases(p,390,0,True,[]);self.assertEqual(p,(True,True,False))
  self.assertEqual(m.observe_phases(p,391,1,True,[]),(True,True,True))
 def test_stale_and_missing_cold_observation_cannot_prove_recovery(self):
  self.assertEqual(m.observe_phases((False,False,False),390,1,True,[]),(False,False,False))
  self.assertEqual(m.observe_phases((True,False,False),380,1,False,[]),(True,False,False))
 def test_window_cannot_span_recorder_gap_or_clock_regression(self):
  self.assertTrue(m.contiguous(None,1));self.assertTrue(m.contiguous(1,15_000_000_001))
  self.assertFalse(m.contiguous(1,36_000_000_001));self.assertFalse(m.contiguous(2,1))
if __name__=='__main__':unittest.main()

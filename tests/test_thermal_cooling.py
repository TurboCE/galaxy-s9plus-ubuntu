# SPDX-License-Identifier: GPL-2.0-only
import importlib.util, unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('cool',Path(__file__).resolve().parents[1]/'experiments/thermal/thermal-control.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CoolingTests(unittest.TestCase):
 def row(self,t=400):return {'end_monotonic_ns':49_000_000_000,'temperature':{n:{'temperature_deci_c':v} for n,v in [('battery',t),('usb',350),('charger',450)]}}
 def test_hysteresis(self):
  self.assertFalse(m.decision(self.row(),50_000_000_000,False)[0])
  self.assertTrue(m.decision(self.row(410),50_000_000_000,False)[0])
  self.assertTrue(m.decision(self.row(),50_000_000_000,True)[0])
  self.assertFalse(m.decision(self.row(390),50_000_000_000,True)[0])
 def test_missing_stale_future_never_release(self):
  for r,n in [({},50_000_000_000),(self.row(380),90_000_000_000),(self.row(380),1)]:self.assertTrue(m.decision(r,n,False)[0])
 def test_hotspot_and_invalid(self):
  r=self.row(380);r['temperature']['charger']['temperature_deci_c']=600
  self.assertTrue(m.decision(r,50_000_000_000,False)[0])
  r=self.row();r['temperature']['battery']['temperature_deci_c']='cold'
  self.assertTrue(m.decision(r,50_000_000_000,False)[0])
 def test_cadence_restore_and_later_external_request(self):
  state={'original':20000,'last':None}
  state,value=m.cadence_request(state,20000,True);self.assertEqual(value,200000)
  state,value=m.cadence_request(state,200000,False);self.assertEqual(value,20000)
  state,value=m.cadence_request(state,300000,True);self.assertEqual(value,300000)
  state,value=m.cadence_request(state,300000,False);self.assertEqual(value,300000)
if __name__=='__main__':unittest.main()

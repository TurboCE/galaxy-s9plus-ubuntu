# SPDX-License-Identifier: GPL-2.0-only
import importlib.util, unittest,tempfile,json
from pathlib import Path
s=importlib.util.spec_from_file_location('cool',Path(__file__).resolve().parents[1]/'experiments/thermal/thermal-control.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CoolingTests(unittest.TestCase):
 def row(self,t=370):return {'end_monotonic_ns':49_000_000_000,'temperature':{n:{'temperature_deci_c':v} for n,v in [('battery',t),('usb',350),('charger',450)]}}
 def test_hysteresis(self):
  self.assertFalse(m.decision(self.row(),50_000_000_000,False)[0])
  self.assertTrue(m.decision(self.row(380),50_000_000_000,False)[0])
  self.assertTrue(m.decision(self.row(),50_000_000_000,True)[0])
  self.assertFalse(m.decision(self.row(360),50_000_000_000,True)[0])
 def test_missing_stale_future_never_release(self):
  for r,n in [({},50_000_000_000),(self.row(360),90_000_000_000),(self.row(360),1)]:self.assertTrue(m.decision(r,n,False)[0])
 def test_hotspot_and_invalid(self):
  r=self.row(360);r['temperature']['charger']['temperature_deci_c']=600
  self.assertTrue(m.decision(r,50_000_000_000,False)[0])
  r=self.row();r['temperature']['battery']['temperature_deci_c']='cold'
  self.assertTrue(m.decision(r,50_000_000_000,False)[0])
 def test_cadence_restore_and_later_external_request(self):
  state={'original':20000,'last':None}
  state,value=m.cadence_request(state,20000,True);self.assertEqual(value,200000)
  state,value=m.cadence_request(state,200000,False);self.assertEqual(value,20000)
  state,value=m.cadence_request(state,300000,True);self.assertEqual(value,300000)
  state,value=m.cadence_request(state,300000,False);self.assertEqual(value,300000)
 def test_display_idle_does_not_latch_temperature_hysteresis(self):
  hot,reason=m.decision(self.row(360),50_000_000_000,True)
  self.assertFalse(hot)
  self.assertEqual(m.cooling_request(hot,reason,True),(True,'screen_off_idle'))
  self.assertEqual(m.cooling_request(hot,reason,False),(False,'normal'))
  self.assertEqual(m.cooling_request(hot,reason,None),(True,'unknown_display_state'))
  self.assertEqual(m.cooling_request(True,'thermal_cooling',False),(True,'thermal_cooling'))
 def test_real_connector_layout_requires_consistent_unique_panel(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.assertIsNone(m.panel_is_off(root))
   p=root/'card7-DSI-1';p.mkdir()
   (p/'enabled').write_text('disabled\n');(p/'dpms').write_text('Off\n')
   self.assertTrue(m.panel_is_off(root))
   (p/'enabled').write_text('enabled\n');self.assertIsNone(m.panel_is_off(root))
   (p/'dpms').write_text('On\n');self.assertFalse(m.panel_is_off(root))
   (root/'card8-DSI-1').mkdir();self.assertIsNone(m.panel_is_off(root))
 def test_concurrent_partial_record_uses_fresh_completed_sample(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'samples';r=self.row(360)
   p.write_text(json.dumps(r)+'\n{"end_monotonic_ns":')
   self.assertEqual(m.latest_completed_sample(p),r)
   self.assertFalse(m.decision(m.latest_completed_sample(p),50_000_000_000,False)[0])
   self.assertTrue(m.decision(m.latest_completed_sample(p),90_000_000_000,False)[0])
   p.write_text('{"end_monotonic_ns":')
   with self.assertRaises(ValueError):m.latest_completed_sample(p)
 def test_same_boot_restart_preserves_cleared_thermal_latch(self):
  state={'boot':'test-current','thermal_hot':False}
  hot=m.restored_hot(state,'test-current');self.assertFalse(hot)
  self.assertFalse(m.decision(self.row(370),50_000_000_000,hot)[0])
  self.assertTrue(m.restored_hot(state,'test-new'))
  self.assertTrue(m.restored_hot({'boot':'test-current','thermal_hot':'invalid'},'test-current'))
if __name__=='__main__':unittest.main()

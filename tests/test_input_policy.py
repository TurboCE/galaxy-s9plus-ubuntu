# SPDX-License-Identifier: GPL-2.0-only
import copy, importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'experiments/charging'/f'{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('input-policy');g=load('charge-guardian')
class InputPolicyTests(unittest.TestCase):
 def test_live_kernel_lease_is_required_for_900ma(self):
  now=50_000_000_000
  row={'input_source_policy':{'source':{'sampled_ms':49900,'queried_ms':49000,'contract_valid':1,'source_uv':5000000,'source_ua':3000000},'control':{'owned':1,'requested':900000,'applied':900000,'deadline_ms':64000}}}
  self.assertEqual(g.input_ceiling(row,now),900000)
  for section,key,value in [('source','contract_valid',0),('source','source_uv',9000000),('source','source_ua',500000),('source','sampled_ms',48000),('source','queried_ms',46000),('source','sampled_ms',51000),('control','owned',0),('control','applied',500000),('control','deadline_ms',50000),('control','deadline_ms',66000)]:
   bad=copy.deepcopy(row);bad['input_source_policy'][section][key]=value
   self.assertEqual(g.input_ceiling(bad,now),500000)
  self.assertEqual(g.input_ceiling({},now),500000)
  higher=copy.deepcopy(row);higher['input_source_policy']['control'].update(requested=1200000,applied=1200000)
  self.assertEqual(g.input_ceiling(higher,now),1200000)
  higher['input_source_policy']['source']['source_ua']=900000
  self.assertEqual(g.input_ceiling(higher,now),500000)
  higher['input_source_policy']['control'].update(requested=1500000,applied=1500000)
  self.assertEqual(g.input_ceiling(higher,now),500000)
 def test_hot_stale_fault_and_missing_adc_forbid_trial(self):
  now=50_000_000_000
  row={'end_monotonic_ns':49_000_000_000,'temperature':{k:{'temperature_deci_c':350} for k in ('battery','usb','charger')},'decoded':{'input':3,'battery':4,'charge':1},'source_initialization_mismatch':{}}
  self.assertTrue(m.permitted(row,now))
  for channel in ('battery','usb','charger'):
   bad=copy.deepcopy(row);bad['temperature'][channel]['temperature_deci_c']=501
   self.assertFalse(m.permitted(bad,now))
  bad=copy.deepcopy(row);bad['end_monotonic_ns']=15_000_000_000;self.assertFalse(m.permitted(bad,now))
  bad=copy.deepcopy(row);bad['decoded']['charge']=6;self.assertFalse(m.permitted(bad,now))
  self.assertFalse(m.permitted({},now))
 def test_external_power_is_allowed_during_charge_hold_but_never_unknown_fault(self):
  state={'hardware_fault':False,'configuration_fault':False,'boot':'test','last':49,'reasons':['swelling_temperature_stop']}
  self.assertTrue(m.guardian_ready(state,50,'test'))
  for reason in ('temperature_limit','invalid_temperature','stale_or_missing_sample','hardware_fault','guardian-stopped'):
   bad=copy.deepcopy(state);bad['reasons']=[reason];self.assertFalse(m.guardian_ready(bad,50,'test'))
  self.assertFalse(m.guardian_ready(state,65,'test'))
  self.assertFalse(m.guardian_ready(state,50,'other-boot'))
  self.assertFalse(m.guardian_ready({},50,'test'))
  row={'end_monotonic_ns':49_000_000_000,'temperature':{k:{'temperature_deci_c':350} for k in ('battery','usb','charger')},'decoded':{'input':3,'battery':4,'charge':8},'source_initialization_mismatch':{}}
  row['temperature']['battery']['temperature_deci_c']=420
  self.assertTrue(m.permitted(row,50_000_000_000))
  row['temperature']['battery']['temperature_deci_c']=431
  self.assertFalse(m.permitted(row,50_000_000_000))

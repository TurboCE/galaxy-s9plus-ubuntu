# SPDX-License-Identifier: GPL-2.0-only
import copy,importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'experiments/charging/soak-check.py'
s=importlib.util.spec_from_file_location('soak',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class SoakTests(unittest.TestCase):
    def setUp(self):
        self.now=50_000_000_000;self.row={'end_monotonic_ns':self.now-1_000_000_000,
            'decoded':{'charge':1,'charge_enabled':1,'input':3},'source_initialization_mismatch':{},
            'shadow_thermal_policy':{'valid':True},'power_supply':{'max77705-charger':{
                'input_current_limit':'500000','constant_charge_current':'450000','constant_charge_voltage':'4350000'}}}

    def test_original_fault_and_configuration_drift_fail(self):
        self.assertEqual(m.classify(self.row,self.now),([],[]))
        row=copy.deepcopy(self.row);row['decoded']['charge']=6
        self.assertIn('hardware_charge_fault',m.classify(row,self.now)[0])
        row=copy.deepcopy(self.row);row['source_initialization_mismatch']={'timer':1}
        self.assertIn('configuration_drift',m.classify(row,self.now)[0])

    def test_stale_or_protected_pause_cannot_pass_continuous_charging(self):
        row=copy.deepcopy(self.row);row['end_monotonic_ns']=0
        self.assertIn('stale_record',m.classify(row,self.now)[1])
        row=copy.deepcopy(self.row);row['decoded'].update(charge=8,charge_enabled=0)
        bad,changed=m.classify(row,self.now);self.assertEqual(bad,[]);self.assertTrue(changed)

    def test_sticky_fault_is_not_lost_when_latest_hardware_is_off(self):
        self.assertIn('latched_hardware_fault',m.classify(self.row,self.now,{'hardware_fault':True})[0])
        self.assertIn('latched_configuration_drift',m.classify(self.row,self.now,{'configuration_fault':True})[0])

    def test_managed_input_requires_qualified_live_lease_without_weakening_legacy(self):
        row=copy.deepcopy(self.row)
        row['power_supply']['max77705-charger']['input_current_limit']='900000'
        self.assertIn('baseline_limits_changed',m.classify(row,self.now)[1])
        self.assertEqual(m.classify(row,self.now,source_policy={'ceiling':900000}),([],[]))
        self.assertIn('input_lease_not_active',m.classify(row,self.now,source_policy={'ceiling':500000})[1])
        self.assertIn('baseline_limits_changed',m.classify(self.row,self.now,source_policy={'ceiling':900000})[1])

if __name__=='__main__':unittest.main()

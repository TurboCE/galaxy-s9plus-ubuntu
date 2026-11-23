# SPDX-License-Identifier: GPL-2.0-only
import copy,importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'experiments/charging/restart-once.py'
s=importlib.util.spec_from_file_location('restart_once',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class RestartOnceTests(unittest.TestCase):
    def setUp(self):
        self.now=50_000_000_000
        self.row={'end_monotonic_ns':self.now-1_000_000_000,
            'decoded':{'charge':6,'battery':2,'input':3,'charge_enabled':1},
            'shadow_thermal_policy':{'valid':True,'thermal_charge_permission':True,'swelling_high_temperature_policy_required':False},
            'temperature':{'battery':{'temperature_deci_c':380}}}
        self.limits={'input_current_limit':'500000','constant_charge_current':'450000','constant_charge_voltage':'4200000'}

    def test_only_exact_fresh_observed_fault_eligible(self):
        self.assertTrue(m.eligible(self.row,self.now,self.limits))
        for age in (-1,30_000_000_000,100_000_000_000):
            row=copy.deepcopy(self.row);row['end_monotonic_ns']=self.now-age
            self.assertFalse(m.eligible(row,self.now,self.limits))
        for name,value in (('charge',11),('battery',5),('input',2),('charge_enabled',0)):
            row=copy.deepcopy(self.row);row['decoded'][name]=value
            self.assertFalse(m.eligible(row,self.now,self.limits))

    def test_protection_and_changed_limits_are_not_bypassed(self):
        for name,value in (('valid',False),('thermal_charge_permission',False),('swelling_high_temperature_policy_required',True)):
            row=copy.deepcopy(self.row);row['shadow_thermal_policy'][name]=value
            self.assertFalse(m.eligible(row,self.now,self.limits))
        for value in (99,400,500):
            row=copy.deepcopy(self.row);row['temperature']['battery']['temperature_deci_c']=value
            self.assertFalse(m.eligible(row,self.now,self.limits))
        limits=dict(self.limits);limits['constant_charge_current']='900000'
        self.assertFalse(m.eligible(self.row,self.now,limits))

if __name__=='__main__':unittest.main()

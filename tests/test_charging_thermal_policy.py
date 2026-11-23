# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'experiments/charging/thermal-policy.py'
s=importlib.util.spec_from_file_location('thermal',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class ThermalTests(unittest.TestCase):
    def temperatures(self,battery=250,usb=250):
        return {k:{'temperature_deci_c':v} for k,v in (('battery',battery),('usb',usb),('charger',300))}

    def test_stock_battery_hot_hysteresis(self):
        policy=m.ThermalPolicy()
        for value,blocked in ((499,False),(500,True),(480,True),(451,True),(450,False),(480,False)):
            self.assertEqual(policy.evaluate(self.temperatures(value))['battery_hot'],blocked)

    def test_cold_and_usb_hysteresis(self):
        policy=m.ThermalPolicy()
        for value,blocked in ((1,False),(0,True),(49,True),(50,False)):
            self.assertEqual(policy.evaluate(self.temperatures(value))['battery_cold'],blocked)
        for value,blocked in ((799,False),(800,True),(751,True),(750,False)):
            self.assertEqual(policy.evaluate(self.temperatures(usb=value))['usb_hot'],blocked)

    def test_swelling_gate_distinct_from_normal_hot(self):
        policy=m.ThermalPolicy()
        for value,swelling in ((409,False),(410,True),(400,True),(390,False)):
            result=policy.evaluate(self.temperatures(value))
            self.assertEqual(result['swelling_high_temperature_policy_required'],swelling)
            self.assertTrue(result['thermal_charge_permission'])

    def test_missing_input_cannot_clear_protection(self):
        policy=m.ThermalPolicy();policy.evaluate(self.temperatures(500))
        result=policy.evaluate({})
        self.assertFalse(result['valid']);self.assertIsNone(result['thermal_charge_permission'])
        self.assertTrue(policy.evaluate(self.temperatures(480))['battery_hot'])
        for value in (None,True,901,-201):
            self.assertFalse(policy.evaluate(self.temperatures(value))['valid'])

if __name__=='__main__':unittest.main()

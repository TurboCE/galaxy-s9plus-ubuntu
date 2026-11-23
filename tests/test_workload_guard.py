# SPDX-License-Identifier: GPL-2.0-only
import copy,importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('workload',Path(__file__).resolve().parents[1]/'experiments/thermal/workload-guard.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class WorkloadGuardTests(unittest.TestCase):
 def test_live_safe_and_critical_values(self):
  r={'end_monotonic_ns':49_000_000_000,'temperature':{'battery':{'temperature_deci_c':400}}}
  self.assertIsNone(m.trip_reason(r,50_000_000_000,3700000))
  self.assertEqual(m.trip_reason(r,50_000_000_000,3549999),'battery_voltage')
  self.assertEqual(m.trip_reason(r,50_000_000_000,3700000,400),'battery_temperature')
  self.assertEqual(m.trip_reason(r,84_000_000_000,3700000),'stale_temperature')
  bad=copy.deepcopy(r);bad['temperature']['battery']['temperature_deci_c']='cold'
  self.assertEqual(m.trip_reason(bad,50_000_000_000,3700000),'invalid_temperature')
  self.assertEqual(m.trip_reason({},50_000_000_000,3700000),'missing_measurement')

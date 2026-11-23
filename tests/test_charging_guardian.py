# SPDX-License-Identifier: GPL-2.0-only
import copy,importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'experiments/charging/charge-guardian.py'
s=importlib.util.spec_from_file_location('guardian',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class GuardianTests(unittest.TestCase):
    def setUp(self):
        self.now=50_000_000_000
        self.row={'end_monotonic_ns':self.now-1_000_000_000,
            'shadow_thermal_policy':{'valid':True,'thermal_charge_permission':True,'swelling_high_temperature_policy_required':False},
            'source_initialization_mismatch':{},'decoded':{'charge':1,'battery':3,'input':3,'charge_enabled':1},
            'power_supply':{'max170xx_battery':{'capacity':'13','voltage_now':'3700000'},
                'max77705-charger':{'online':'1','constant_charge_current':'450000','input_current_limit':'500000','constant_charge_voltage':'4350000'}}}

    def evaluate(self,row=None,wall=0,equivalent=0):return m.reasons(row or self.row,self.now,wall,equivalent)

    def test_normal_data_and_explicit_manual_off_not_overridden(self):
        self.assertEqual(self.evaluate(),[])
        row=copy.deepcopy(self.row);row['decoded'].update(charge=8,charge_enabled=0)
        self.assertEqual(self.evaluate(row),[])

    def test_freshness_temperature_and_configuration_fail_closed(self):
        row=copy.deepcopy(self.row);row['end_monotonic_ns']=self.now-35_000_000_000
        self.assertIn('stale_or_missing_sample',self.evaluate(row))
        for field in ('valid','thermal_charge_permission'):
            row=copy.deepcopy(self.row);row['shadow_thermal_policy'][field]=False
            self.assertTrue(self.evaluate(row))
        row=copy.deepcopy(self.row);row['shadow_thermal_policy']['swelling_high_temperature_policy_required']=True
        self.assertIn('swelling_temperature_stop',self.evaluate(row))
        row=copy.deepcopy(self.row);row['source_initialization_mismatch']={'fast_timer':1}
        self.assertIn('charger_configuration_drift',self.evaluate(row))
        del row['source_initialization_mismatch'];self.assertIn('invalid_chip_configuration',self.evaluate(row))

    def test_hardware_fault_and_unqualified_limits(self):
        for charge in (5,6,7,10,11,12,99):
            row=copy.deepcopy(self.row);row['decoded']['charge']=charge
            self.assertIn('hardware_fault',self.evaluate(row))
        row=copy.deepcopy(self.row);row['decoded']['battery']=5
        self.assertIn('battery_fault',self.evaluate(row))
        for field,value in (('constant_charge_current','500000'),('input_current_limit','900000'),('constant_charge_voltage','4400000')):
            row=copy.deepcopy(self.row);row['power_supply']['max77705-charger'][field]=value
            self.assertIn('unqualified_charge_limits',self.evaluate(row))

    def test_missing_chip_readback_does_not_latch_a_hardware_fault(self):
        row=copy.deepcopy(self.row);row['decoded']={}
        blocked=self.evaluate(row)
        self.assertIn('invalid_chip_status',blocked);self.assertNotIn('hardware_fault',blocked)
        state={};m.update_latches(state,row,blocked,'1',{'requested':1,'blocked':1,'actual':0})
        self.assertFalse(state.get('hardware_fault',False))

    def test_input_lease_does_not_override_battery_charge_temperature_gate(self):
        row=copy.deepcopy(self.row)
        row['power_supply']['max77705-charger']['input_current_limit']='1200000'
        row['input_source_policy']={'source':{'sampled_ms':49900,'queried_ms':49000,'contract_valid':1,'source_uv':5000000,'source_ua':3000000},
            'control':{'owned':1,'requested':1200000,'applied':1200000,'deadline_ms':64000}}
        row['shadow_thermal_policy']['swelling_high_temperature_policy_required']=True
        blocked=self.evaluate(row)
        self.assertIn('swelling_temperature_stop',blocked)
        self.assertNotIn('unqualified_charge_limits',blocked)

    def test_stock_time_and_full_boundary(self):
        self.assertEqual(self.evaluate(wall=35999,equivalent=10799),[])
        self.assertIn('safety_time_expired',self.evaluate(wall=36000))
        self.assertIn('safety_time_expired',self.evaluate(equivalent=10800))
        row=copy.deepcopy(self.row);row['decoded']['charge']=4;row['power_supply']['max170xx_battery'].update(capacity='93',voltage_now='4350000')
        self.assertIn('full_stop',self.evaluate(row))
        row['power_supply']['max170xx_battery']['capacity']='92';self.assertNotIn('full_stop',self.evaluate(row))


class RecoveryTests(unittest.TestCase):
    def test_full_hold_survives_chg_off_and_recharge_has_hysteresis(self):
        state={'wall':100,'equivalent':20}
        row={'power_supply':{'max170xx_battery':{'voltage_now':'4350000'}}}
        c={'requested':1,'blocked':1,'actual':0}
        self.assertIn('full_stop',m.update_latches(state,row,['full_stop'],'1',c))
        row['power_supply']['max170xx_battery']['voltage_now']='4340000'
        self.assertIn('full_hold',m.update_latches(state,row,[],'1',c))
        row['power_supply']['max170xx_battery']['voltage_now']='4280000'
        self.assertEqual(m.update_latches(state,row,[],'1',c),[])
        self.assertFalse(state['full_hold']);self.assertTrue(state['recharging'])
        self.assertEqual(state['wall'],0);self.assertEqual(state['equivalent'],0)

    def test_fault_latch_not_cleared_by_its_own_disable(self):
        state={'wall':100,'equivalent':20};row={};c={'requested':1,'blocked':1,'actual':0}
        m.update_latches(state,row,['hardware_fault'],'1',c)
        self.assertIn('hardware_fault',m.update_latches(state,row,[],'1',c))
        m.update_latches(state,row,[],'0',c)
        self.assertEqual(m.update_latches(state,row,[],'1',c),[])

    def test_unexpected_bit_loss_is_not_an_automatic_enable(self):
        state={};control={'requested':1,'blocked':0,'actual':0}
        self.assertIn('unexpected_hardware_disable',m.update_latches(state,{},[],'1',control))
        self.assertTrue(state['hardware_fault'])

    def test_policy_transactions_never_use_legacy_auto_and_tolerate_manual_race(self):
        import tempfile,errno
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'device').mkdir();path=root/'device/charge_policy_request';path.write_text('unchanged')
            with patch.object(m,'CHARGER',root):
                m.policy_allow(True,[],{'generation':3,'requested':0,'blocked':0,'actual':0})
                self.assertEqual(path.read_text(),'unchanged')
                m.policy_allow(True,[],{'generation':3,'requested':0,'blocked':1,'actual':0})
                self.assertEqual(path.read_text(),'3 1\n')
                with patch.object(Path,'write_text',side_effect=BlockingIOError(errno.EAGAIN,'manual request raced')):
                    m.policy_allow(True,[],{'generation':3,'requested':1,'blocked':1,'actual':0})
            self.assertFalse((root/'charge_behaviour').exists())


class SleepLeaseTests(unittest.TestCase):
    def test_only_owned_inhibitor_group_released_on_unplug(self):
        from unittest.mock import Mock,patch
        proc=Mock(pid=23456);proc.poll.return_value=None
        with patch.object(m.subprocess,'Popen',return_value=proc) as popen,patch.object(m.os,'killpg') as kill,patch.object(m.time,'sleep'):
            lease=m.SleepLease();self.assertTrue(lease.update(True));self.assertTrue(lease.update(True));self.assertEqual(popen.call_count,1)
            self.assertTrue(lease.update(False));kill.assert_called_once_with(proc.pid,m.signal.SIGTERM)
            self.assertIsNone(lease.process)

    def test_unavailable_inhibitor_is_not_reported_ready(self):
        from unittest.mock import patch
        with patch.object(m.subprocess,'Popen',side_effect=OSError('missing')):
            self.assertFalse(m.SleepLease().update(True))


class HardwareWatchdogTests(unittest.TestCase):
    def run_case(self, before, after=None, blocked=(), fresh=True):
        import tempfile
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            h=m.HardwareWatchdog.__new__(m.HardwareWatchdog);h.params=Path(directory)
            feed=h.params/'feed';feed.write_text('untouched')
            h.status=Mock(side_effect=[before, after or before])
            row={'end_monotonic_ns':10_000_000_000 if fresh else 0,
                 'shadow_thermal_policy':{'valid':True}}
            value=h.update(row,45_000_000_000 if not fresh else 11_000_000_000,list(blocked),'1')
            return value,feed.read_text()

    def test_arm_requires_actual_charge_inhibit_and_checks_enabled_readback(self):
        before={'owned':0,'wdt_enabled':0,'charge_enabled':1,'owned_expiry_seen':0,'details1':49}
        reasons,text=self.run_case(before)
        self.assertIn('hardware_watchdog_waiting_inhibit',reasons);self.assertEqual(text,'untouched')
        before.update(charge_enabled=0,details1=56)
        after=dict(before,owned=1,wdt_enabled=1)
        self.assertEqual(self.run_case(before,after),([], '1\n'))
        with self.assertRaises(RuntimeError):self.run_case(before)

    def test_expiry_or_lost_ownership_never_feeds(self):
        before={'owned':1,'wdt_enabled':1,'charge_enabled':0,'owned_expiry_seen':1,'details1':56}
        reasons,text=self.run_case(before)
        self.assertIn('hardware_watchdog_expired',reasons);self.assertEqual(text,'untouched')
        before.update(owned_expiry_seen=0,wdt_enabled=0)
        reasons,text=self.run_case(before)
        self.assertIn('hardware_watchdog_ownership_lost',reasons);self.assertEqual(text,'untouched')

    def test_stale_or_fault_data_does_not_extend_hardware_timeout(self):
        before={'owned':1,'wdt_enabled':1,'charge_enabled':0,'owned_expiry_seen':0,'details1':56}
        self.assertEqual(self.run_case(before,fresh=False),([], 'untouched'))
        for reason in ('hardware_fault','charger_configuration_drift','invalid_temperature'):
            self.assertEqual(self.run_case(before,blocked=[reason]),([], 'untouched'))
        self.assertEqual(self.run_case(before,blocked=['swelling_temperature_stop']),([], '1\n'))
        before['charge_enabled']=1
        reasons,text=self.run_case(before,blocked=['swelling_temperature_stop'])
        self.assertIn('hardware_watchdog_waiting_inhibit',reasons);self.assertEqual(text,'untouched')

if __name__=='__main__':unittest.main()

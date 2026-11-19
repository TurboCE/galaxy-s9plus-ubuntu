# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('restore',Path(__file__).resolve().parents[1]/'scripts/g965n/sensor-trial-restore.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RestoreTests(unittest.TestCase):
    def state(self,mode='native',connector='DSI-1'):
        return (9,[((connector,'vendor','panel',''),[(mode,1440,2960,60.,2.,[1.,2.],{'is-current':True})],{})],[(0,0,2.,0,True,[(connector,'vendor','panel','')],{})],{'layout-mode':1})
    def test_actual_abi_snapshot_uses_fresh_serial_and_temporary_method_data(self):
        saved=m.display_snapshot(self.state());serial,logical=m.restore_parameters(saved,self.state())
        self.assertEqual(serial,9);self.assertEqual(logical,[(0,0,2.,0,True,[('DSI-1','native',{})])]);self.assertEqual(saved['layout_mode'],1)
    def test_changed_monitor_or_missing_mode_refused(self):
        saved=m.display_snapshot(self.state())
        for state in (self.state(connector='HDMI-1'),self.state(mode='different')):
            with self.assertRaises(ValueError):m.restore_parameters(saved,state)
    def test_empty_current_display_not_a_snapshot(self):
        with self.assertRaises(ValueError):m.display_snapshot((0,[],[],{}))
if __name__=='__main__':unittest.main()

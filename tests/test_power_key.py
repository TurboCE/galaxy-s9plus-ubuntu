# SPDX-License-Identifier: GPL-2.0-only
import importlib.util,tempfile,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'experiments/display-power/power-key.py'
s=importlib.util.spec_from_file_location('power_key',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class PowerKeyTests(unittest.TestCase):
 def test_only_a_debounced_press_toggles_not_release_repeat_or_other_keys(self):
  self.assertTrue(m.power_press(1,116,1,None,0))
  self.assertTrue(m.power_press(1,116,1,0,.75))
  for args in [(1,116,0,None,0),(1,116,2,None,0),(1,115,1,None,0),(0,116,1,None,0),(1,116,1,1,1.74),(1,116,1,10,9)]:self.assertFalse(m.power_press(*args))
 def test_mode_toggle_refuses_unsupported(self):
  self.assertEqual(m.target_mode(0),3)
  for v in (1,2,3):self.assertEqual(m.target_mode(v),0)
  for v in (-1,4,99):
   with self.assertRaises(RuntimeError):m.target_mode(v)
 def test_native_wake_from_same_press_is_not_toggled_off_again(self):
  from unittest.mock import MagicMock,patch
  panel=MagicMock();panel.__truediv__.return_value.read_text.return_value='On\n'
  wake=MagicMock()
  with patch.object(m,'get_mode',return_value=0),patch.object(m,'command',return_value='()') as command,patch.object(m.Path,'glob',return_value=[panel]):
   self.assertEqual(m.toggle([],before=3,wake=wake),'On');wake.emit.assert_called_once()
   command.assert_not_called()  # Native user-input wake only; no competing DPMS write.
 def test_bitmap_order_and_unique_gpio_key(self):
  self.assertEqual(m.bitmap('10000000000000 0'),1<<116)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   def add(n,name,keys):
    p=root/n/'device';(p/'capabilities').mkdir(parents=True);(p/'name').write_text(name);(p/'capabilities/key').write_text(keys)
   add('event0','gpio-keys','10000000000000 0')
   add('event1','keyboard','10000000000000 0')
   self.assertEqual(m.discover(root),Path('/dev/input/event0'))
   add('event2','gpio-keys','10000000000000 0')
   with self.assertRaises(RuntimeError):m.discover(root)

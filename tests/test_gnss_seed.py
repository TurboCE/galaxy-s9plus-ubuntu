# SPDX-License-Identifier: GPL-2.0-only
import importlib.util,math,time,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('seed',Path(__file__).parents[1]/'experiments/gnss/seed.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SeedTests(unittest.TestCase):
 def sample(self):return dict(source='network',lat=10.,lon=20.,accuracy=25000.,time=1000.)
 def test_uncertainty_grows_without_mutating_cache(self):
  r=self.sample();self.assertEqual(m.validate(r,1010)['accuracy'],28500);self.assertEqual(m.validate(r,1010)['sample_accuracy'],25000);self.assertEqual(r['accuracy'],25000)
 def test_invalid_or_stale_never_injected(self):
  for key,vals in {'lat':[True,91,float('nan')],'lon':[-181,float('inf')],'accuracy':[0,100001],'time':[1001,699],'source':['unknown']}.items():
   for val in vals:
    r=self.sample();r[key]=val;self.assertIsNone(m.validate(r,1000),(key,val))
  self.assertIsNone(m.validate(self.sample(),1300)) # travel uncertainty exceeds cap
 def test_only_fresh_real_gps_fixes_cached(self):
  stamp=time.time()-2
  import datetime
  r=dict(type='irrelevant',**{'class':'TPV','mode':3,'time':datetime.datetime.fromtimestamp(stamp,datetime.timezone.utc).isoformat(),'lat':10,'lon':20,'epx':3,'epy':4})
  self.assertEqual(m.gps_fix(r,stamp+2)['accuracy'],5)
  r['mode']=1;self.assertIsNone(m.gps_fix(r,stamp+2));r['mode']=3
  self.assertIsNone(m.gps_fix(r,stamp+20));r['epy']=float('nan');self.assertIsNone(m.gps_fix(r,stamp+2))
  r['epy']=4;r['time']=datetime.datetime.fromtimestamp(stamp).isoformat();self.assertIsNone(m.gps_fix(r,stamp+2))
if __name__=='__main__':unittest.main()

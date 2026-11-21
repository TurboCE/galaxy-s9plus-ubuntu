# SPDX-License-Identifier: GPL-2.0-only
import importlib.util,json,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('receiver_status',Path(__file__).parents[1]/'experiments/gnss/receiver-status.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def sentence(body):
 b=body.encode();checksum=0
 for value in b:checksum^=value
 return b'$'+b+b'*'+('%02X'%checksum).encode()
class ReceiverStatusTests(unittest.TestCase):
 def sample(self):
  return 'PGLOR,9,STA,123456.00,0,4294.967,0,2000,9999,0,P,F,L,0,C,0,S,0000,0,0,R,0000,tPeF,0,1234,LC'
 def test_aggregate_metadata_excludes_clock_and_payload(self):
  r=m.ReceiverStatus();r.feed(sentence(self.sample()));v=r.summary()
  self.assertEqual(v['aid_flags'],{'tPeF':1});self.assertEqual(v['time_source_codes'],[0])
  self.assertEqual(v['numeric_ranges']['satellite_ephemeris_count'],[0,0])
  self.assertNotIn('123456',json.dumps(v));self.assertNotIn('1234',json.dumps(v))
 def test_position_records_and_unknown_payload_never_exported(self):
  r=m.ReceiverStatus();r.feed(sentence('GPGGA,123456,3712.345,N,12734.567,E'))
  r.feed(sentence('PGLOR,1,UNC,private-identifier,3712.345,12734.567'))
  self.assertNotIn('private',json.dumps(r.summary()));self.assertNotIn('3712',json.dumps(r.summary()))
 def test_bad_checksum_or_layout_not_decoded(self):
  r=m.ReceiverStatus();r.feed(sentence(self.sample())[:-1]+b'Z')
  self.assertEqual(r.summary()['pglor_types'],{})
  r.feed(sentence(self.sample().replace(',P,F,',',X,F,')))
  self.assertEqual(r.summary()['common_sta_prefix_records'],0)
 def test_nonfinite_fields_and_unsupported_version(self):
  r=m.ReceiverStatus();r.feed(sentence(self.sample().replace('4294.967','nan')))
  self.assertNotIn('sta_field_5',r.summary()['numeric_ranges'])
  r=m.ReceiverStatus();r.feed(sentence(self.sample().replace('PGLOR,9,','PGLOR,255,')))
  self.assertEqual(r.summary()['numeric_ranges'],{})
if __name__=='__main__':unittest.main()

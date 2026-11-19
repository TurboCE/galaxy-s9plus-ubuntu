# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('heading',ROOT/'experiments/sensors/heading-math.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
IDENTITY=[1,0,0,0,1,0,0,0,1]

def rotate_x(v,degrees):
 a=math.radians(degrees);x,y,z=v
 return (x,y*math.cos(a)-z*math.sin(a),y*math.sin(a)+z*math.cos(a))

class HeadingMathTests(unittest.TestCase):
 def test_cardinals_and_pitch_invariance_for_actual_vector_geometry(self):
  for expected in (0,45,90,180,270,359):
   a=math.radians(expected);field=(-300*math.sin(a),300*math.cos(a),-400)
   for pitch in (-50,0,50):
    heading=h.diagnostic_heading(rotate_x((0,0,4096),pitch),(*rotate_x(field,pitch),3,0),IDENTITY,IDENTITY)
    error=(heading-expected+180)%360-180
    self.assertAlmostEqual(error,0,places=8)
 def test_quality_overflow_gravity_and_unobservable_heading_rejected(self):
  for acceleration,magnetic in [((0,0,4096),(0,300,-400,1,0)),
       ((0,0,4096),(0,300,-400,3,1)),((0,0,1),(0,300,-400,3,0)),
       ((0,0,4096),(0,0,-400,3,0)),((0,4096,0),(300,0,-400,3,0))]:
   with self.assertRaises(ValueError):h.diagnostic_heading(acceleration,magnetic,IDENTITY,IDENTITY)
 def test_reflection_or_unqualified_scale_cannot_be_a_mount_rotation(self):
  for matrix in ([1,0,0,0,1,0,0,0,-1],[2,0,0,0,1,0,0,0,1],[1,0,0]*3):
   with self.assertRaises(ValueError):h.mounted((1,2,3),matrix)
 def test_host_pairing_is_bounded_and_never_qualifies_hardware(self):
  rows=[{'receive_monotonic_s':1.,'samples':{'0':[(0,0,4096)]}},
        {'receive_monotonic_s':1.3,'samples':{'4':[(0,300,-400,3,0)]}},
        {'receive_monotonic_s':1.4,'samples':{'0':[(0,0,4096)],'4':[(0,300,-400,3,0)]}}]
  result=h.evaluate(rows,IDENTITY,IDENTITY)
  self.assertEqual(result['usable_batches'],1)
  self.assertEqual(result['excluded'],{'No close acceleration receive batch':1})
  self.assertTrue(result['diagnostic_only']);self.assertFalse(result['heading_qualified'])
  self.assertEqual(result['diagnostic_magnetic_heading_deg'],0)
  with self.assertRaises(ValueError):h.evaluate(list(reversed(rows)),IDENTITY,IDENTITY)

if __name__=='__main__':unittest.main()

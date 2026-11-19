# SPDX-License-Identifier: GPL-2.0-only
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('orientation', Path(__file__).resolve().parents[1] / 'scripts/g965n/sensor-orientation.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)


def synthetic():
    values = {'top-right':[4096,0,0], 'top-left':[-4096,0,0],
              'top-up':[0,-4096,0], 'bottom-up':[0,4096,0],
              'face-up':[0,0,4096], 'face-down':[0,0,-4096]}
    return {'reference': {'range_g':8, 'range_verified':True,
                         'sensor_frame_handedness':'right', 'frame_basis':'synthetic right-handed fixture',
                         'z_positive_pose':'face-up', 'z_basis':'synthetic reference only'},
            'poses': {p:[list(v) for _ in range(12)] for p,v in values.items()}}


class OrientationTests(unittest.TestCase):
    def test_identity_and_nontrivial_signed_permutation(self):
        data = synthetic()
        self.assertEqual(o.evaluate(data)['mount_matrix'], '1,0,0;0,1,0;0,0,1')
        for frames in data['poses'].values():
            for f in frames:
                f[:] = [-f[1], f[0], f[2]]
        self.assertEqual(o.evaluate(data)['mount_matrix'], '0,1,0;-1,0,0;0,0,1')
        self.assertFalse(o.evaluate(data)['installed'])

    def test_missing_reference_wrong_range_and_reflection_rejected(self):
        for key, value in [('z_basis',''), ('z_positive_pose',None), ('range_g',4),
                           ('range_verified',False), ('frame_basis',''), ('sensor_frame_handedness','unknown')]:
            data = synthetic(); data['reference'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                o.evaluate(data)
        data = synthetic(); data['reference']['z_positive_pose'] = 'face-down'
        with self.assertRaisesRegex(ValueError, 'reflection'):
            o.evaluate(data)

    def test_unstable_tilted_wrong_magnitude_missing_or_short_pose(self):
        mutations = [lambda d: d['poses']['top-up'].__setitem__(0,[0,-1000,0]),
                     lambda d: d['poses'].__setitem__('top-up',[[2900,-2900,0]]*12),
                     lambda d: d['poses'].__setitem__('top-up',[[0,-8000,0]]*12),
                     lambda d: d['poses'].pop('face-down'),
                     lambda d: d['poses'].__setitem__('face-up',[[0,0,4096]]*7)]
        for change in mutations:
            data = synthetic(); change(data)
            with self.assertRaises(ValueError):
                o.evaluate(data)

    def test_opposite_and_nonindependent_vectors_rejected(self):
        data = synthetic(); data['poses']['top-left'] = copy.deepcopy(data['poses']['top-right'])
        with self.assertRaisesRegex(ValueError,'Opposite'):
            o.evaluate(data)
        data = synthetic()
        data['poses']['face-up'] = copy.deepcopy(data['poses']['top-right'])
        data['poses']['face-down'] = copy.deepcopy(data['poses']['top-left'])
        with self.assertRaisesRegex(ValueError,'independent'):
            o.evaluate(data)

    def test_invalid_numeric_data_and_minimum(self):
        for data in ([], {'reference':None}, dict(synthetic(), poses=[])):
            with self.assertRaises(ValueError):
                o.evaluate(data)
        for value in (float('nan'),float('inf'),True,'4096',32768):
            data = synthetic(); data['poses']['face-up'][0][2] = value
            with self.assertRaises(ValueError):
                o.evaluate(data)
        with self.assertRaises(ValueError):
            o.evaluate(synthetic(), minimum=1)

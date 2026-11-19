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


class HandheldOrientationTests(unittest.TestCase):
    def tilted(self, degrees=10, magnitude=1.0):
        import math
        d = synthetic()
        g = o.G_COUNTS*magnitude
        major, minor = g*math.cos(math.radians(degrees)), g*math.sin(math.radians(degrees))
        # Each opposite pair has equal common posture tilt, not sensor bias.
        values = {'top-right':[major,0,minor], 'top-left':[-major,0,minor],
                  'bottom-up':[0,major,minor], 'top-up':[0,-major,minor],
                  'face-up':[minor,0,major], 'face-down':[minor,0,-major]}
        d['poses'] = {p:[list(v) for _ in range(12)] for p,v in values.items()}
        return d

    def test_common_ten_degree_tilt_explicit_only_and_discrete_result(self):
        data = self.tilted()
        with self.assertRaises(ValueError):
            o.evaluate(data)  # Strict original policy is unchanged.
        result = o.evaluate(data, handheld=True)
        self.assertEqual(result['mount_matrix'], '1,0,0;0,1,0;0,0,1')
        self.assertEqual(result['qualification'], 'discrete axis assignment only')
        self.assertEqual(result['capture_mode'], 'handheld-15deg')
        self.assertAlmostEqual(result['capture_tilt_degrees']['top-up'], 10)
        self.assertAlmostEqual(result['pair_fit']['top-right/top-left']['difference_axis_degrees'], 0)
        self.assertGreater(result['pair_fit']['top-right/top-left']['common_off_axis_g'], .17)

    def test_same_gravity_wrong_yaw_and_twenty_degree_capture_fail(self):
        d = self.tilted(); d['poses']['top-left'] = copy.deepcopy(d['poses']['top-right'])
        with self.assertRaisesRegex(ValueError,'opposite dominant signs'):
            o.evaluate(d, handheld=True)
        d = self.tilted(); d['poses']['top-right'] = copy.deepcopy(d['poses']['top-up'])
        with self.assertRaisesRegex(ValueError,'dominant axes'):
            o.evaluate(d, handheld=True)
        with self.assertRaisesRegex(ValueError,'tilted'):
            o.evaluate(self.tilted(20), handheld=True)

    def test_pair_common_tilt_range_reference_and_stale_format_still_fail(self):
        with self.assertRaisesRegex(ValueError,'common tilt'):
            o.evaluate(self.tilted(14, 1.12), handheld=True)
        d = self.tilted(); d['reference']['range_g'] = 4
        with self.assertRaisesRegex(ValueError,'full-scale'):
            o.evaluate(d, handheld=True)
        d = self.tilted(); d['reference'].pop('z_basis')
        with self.assertRaisesRegex(ValueError,'Z sign'):
            o.evaluate(d, handheld=True)
        d = self.tilted(); d['reference']['z_positive_pose'] = 'face-down'
        with self.assertRaisesRegex(ValueError,'reflection'):
            o.evaluate(d, handheld=True)
        d = self.tilted(); d['poses'] = {'old_samples': d['poses']['top-up']}
        with self.assertRaisesRegex(ValueError,'stable frames'):
            o.evaluate(d, handheld=True)

    def test_unstable_and_nonindependent_poses_not_relaxed(self):
        d = self.tilted(); d['poses']['top-up'][0][1] += 500
        with self.assertRaisesRegex(ValueError,'unstable'):
            o.evaluate(d, handheld=True)
        d = self.tilted()
        d['poses']['face-up'] = copy.deepcopy(d['poses']['top-right'])
        d['poses']['face-down'] = copy.deepcopy(d['poses']['top-left'])
        with self.assertRaisesRegex(ValueError,'independent'):
            o.evaluate(d, handheld=True)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Validate explicit six-pose measurements; print an unapplied IIO matrix.

Independent signed-permutation mathematics, not iio-sensor-proxy algorithm code.
No device access, profile installation or fallback to guessed axes.
"""
import argparse
import json
import math
import statistics

POSES = ('top-up', 'top-right', 'top-left', 'bottom-up', 'face-up', 'face-down')
G_COUNTS = 4096.0  # Pinned LSM6DSL 8G factory calibration MAX_ACCEL_1G.


def norm(vector):
    return math.sqrt(sum(v * v for v in vector))


def distance(a, b):
    return norm([x - y for x, y in zip(a, b)])


def stable_vector(frames, minimum):
    if not isinstance(frames, list) or len(frames) < minimum:
        raise ValueError('Each pose requires enough stable frames')
    for frame in frames:
        if (not isinstance(frame, list) or len(frame) != 3 or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                    not math.isfinite(v) or not -32768 <= v <= 32767 for v in frame)):
            raise ValueError('Expected finite signed16 XYZ observations')
    median = [statistics.median(frame[i] for frame in frames) for i in range(3)]
    if any(distance(frame, median) > .08 * G_COUNTS for frame in frames):
        raise ValueError('Pose is unstable; do not infer a mounting matrix')
    if any(not .85 * G_COUNTS <= norm(frame) <= 1.15 * G_COUNTS for frame in frames):
        raise ValueError('Pose magnitude is inconsistent with verified 8G/4096-per-g')
    dominant = max(range(3), key=lambda i: abs(median[i]))
    if (abs(median[dominant]) < .9 * G_COUNTS or
            any(abs(median[i]) > .2 * G_COUNTS for i in range(3) if i != dominant)):
        raise ValueError('Pose is tilted or axis selection is ambiguous')
    return median, dominant


def determinant(matrix):
    a, b, c = matrix
    return (a[0] * (b[1]*c[2] - b[2]*c[1]) -
            a[1] * (b[0]*c[2] - b[2]*c[0]) +
            a[2] * (b[0]*c[1] - b[1]*c[0]))


def evaluate(observations, minimum=12):
    if not isinstance(observations, dict):
        raise ValueError('Expected an observations object')
    if minimum < 8:
        raise ValueError('At least eight stable frames per pose are required')
    reference = observations.get('reference', {})
    if not isinstance(reference, dict):
        raise ValueError('Expected an explicit reference object')
    if reference.get('range_g') != 8 or reference.get('range_verified') is not True:
        raise ValueError('Require actual E1 full-scale=8G verification')
    if (reference.get('sensor_frame_handedness') != 'right' or
            not isinstance(reference.get('frame_basis'), str) or not reference['frame_basis'].strip()):
        raise ValueError('Require explicit right-handed sensor-frame evidence')
    positive_z = reference.get('z_positive_pose')
    if (positive_z not in ('face-up', 'face-down') or
            not isinstance(reference.get('z_basis'), str) or not reference['z_basis'].strip()):
        raise ValueError('Z sign needs an explicit physical reference; never guess it')
    frames = observations.get('poses', {})
    if not isinstance(frames, dict):
        raise ValueError('Expected named physical poses')
    vectors, axes = {}, {}
    for pose in POSES:
        vectors[pose], axes[pose] = stable_vector(frames.get(pose), minimum)
    for positive, negative in (('top-right', 'top-left'), ('bottom-up', 'top-up'), ('face-up', 'face-down')):
        if axes[positive] != axes[negative] or norm([a+b for a,b in zip(vectors[positive], vectors[negative])]) > .12 * G_COUNTS:
            raise ValueError('Opposite poses are inconsistent')
    # Target ABI: top-to-right/left-edge-up => +X; bottom-up => +Y.
    # Z reference is explicitly supplied rather than inferred from X/Y.
    positives = ('top-right', 'bottom-up', positive_z)
    if len({axes[p] for p in positives}) != 3:
        raise ValueError('Pose axes are not independent')
    for i, p in enumerate(positives):
        for q in positives[i+1:]:
            cosine = abs(sum(a*b for a,b in zip(vectors[p], vectors[q]))) / (norm(vectors[p])*norm(vectors[q]))
            if cosine > .15:
                raise ValueError('Pose vectors are not orthogonal')
    matrix = []
    for pose in positives:
        row = [0, 0, 0]
        row[axes[pose]] = 1 if vectors[pose][axes[pose]] > 0 else -1
        matrix.append(row)
    if determinant(matrix) != 1:
        raise ValueError('Reference implies a reflection; verify Z/handedness rather than flip silently')
    return {'geometry_validated': True, 'installed': False,
            'mount_matrix': ';'.join(','.join(str(v) for v in row) for row in matrix),
            'matrix': matrix, 'minimum_frames': minimum,
            'range_g': 8, 'scale_m_s2_per_count': 9.80665/G_COUNTS,
            'limits': 'Input provenance and physical pose labels require independent operator validation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('observations', help='Private JSON observations; never commit actual measurements')
    parser.add_argument('--minimum-frames', type=int, default=12)
    args = parser.parse_args()
    try:
        with open(args.observations, encoding='utf-8') as source:
            result = evaluate(json.load(source), args.minimum_frames)
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(2, 'Unqualified orientation profile: ' + str(error) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

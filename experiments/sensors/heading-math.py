#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline magnetic-heading diagnostic; never installs/publishes a backend.

Vector geometry is original code. A numerically correct result does not
qualify the supplied magnetic mounting matrix, board calibration, heading
accuracy or time synchronization. Inputs are private actual capture batches.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def norm(a):
    return math.sqrt(dot(a, a))


def cross(a, b):
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])


def mounted(raw, matrix):
    if (len(raw) != 3 or any(not math.isfinite(x) for x in raw) or
            len(matrix) != 9 or any(type(x) is not int or x not in (-1, 0, 1) for x in matrix)):
        raise ValueError('Invalid vector or signed matrix')
    rows = [matrix[i:i+3] for i in (0, 3, 6)]
    if (any(sum(x*x for x in row) != 1 for row in rows) or
            any(dot(rows[i], rows[j]) != 0 for i, j in ((0, 1), (0, 2), (1, 2))) or
            dot(rows[0], cross(rows[1], rows[2])) != 1):
        raise ValueError('Mount matrix must be a proper signed-axis rotation')
    return tuple(dot(row, raw) for row in rows)


def diagnostic_heading(acceleration, magnetic, accel_matrix, mag_matrix,
                       minimum_accuracy=2):
    if (len(magnetic) != 5 or type(magnetic[3]) is not int or
            magnetic[3] not in range(4) or magnetic[3] < minimum_accuracy):
        raise ValueError('Magnetic calibration quality too low or invalid')
    if magnetic[4] != 0:
        raise ValueError('Magnetic overflow')
    up = mounted(acceleration, accel_matrix)
    strength = norm(up)
    # This port qualifies actual8G raw scale, approximately4096counts/g.
    if not 0.85 * 4096 <= strength <= 1.15 * 4096:
        raise ValueError('Acceleration not near stationary gravity')
    up = tuple(x/strength for x in up)
    field = mounted(magnetic[:3], mag_matrix)
    north = tuple(x - dot(field, up)*z for x, z in zip(field, up))
    horizontal = norm(north)
    if not norm(field) or horizontal < 0.1 * norm(field):
        raise ValueError('Horizontal magnetic field is indeterminate')
    north = tuple(x/horizontal for x in north)
    east = cross(north, up)
    forward = (0., 1., 0.)  # Physical phone top in the explicitly supplied display frame.
    if math.sqrt(max(0., 1 - dot(forward, up)**2)) < 0.2:
        raise ValueError('Phone top nearly vertical; heading indeterminate')
    return math.degrees(math.atan2(dot(forward, east), dot(forward, north))) % 360


def evaluate(rows, accel_matrix, mag_matrix, minimum_accuracy=2):
    last_accel = None
    angles = []
    skipped = Counter()
    previous = -math.inf
    for row in rows:
        when = row['receive_monotonic_s']
        if not math.isfinite(when) or when < previous:
            raise ValueError('Capture receive clock is not monotonic')
        previous = when
        values = row['samples']
        if values.get('0'):
            last_accel = (when, values['0'][-1])
        if not values.get('4'):
            continue
        if last_accel is None or when-last_accel[0] > .25:
            skipped['No close acceleration receive batch'] += 1
            continue
        try:
            angle = diagnostic_heading(last_accel[1], values['4'][-1], accel_matrix,
                                       mag_matrix, minimum_accuracy)
        except ValueError as error:
            skipped[str(error)] += 1
            continue
        angles.append(angle)
    result = {'diagnostic_only': True, 'heading_qualified': False,
              'association': 'host receive batches, not hardware synchronized',
              'usable_batches': len(angles), 'excluded': dict(skipped)}
    if angles:
        x = sum(math.cos(math.radians(a)) for a in angles)
        y = sum(math.sin(math.radians(a)) for a in angles)
        concentration = math.hypot(x, y)/len(angles)
        result['circular_concentration'] = concentration
        if concentration >= .95:
            result['diagnostic_magnetic_heading_deg'] = math.degrees(math.atan2(y, x)) % 360
    return result


def matrix_arg(value):
    values = [int(x) for x in value.split(',')]
    mounted((0, 0, 0), values)
    return values


def capture_rows(path):
    if path.suffix != '.jsonl':
        yield from json.loads(path.read_bytes())['rows']
        return
    with path.open(encoding='utf-8') as stream:
        header = json.loads(stream.readline())
        if header != {'schema': 1, 'kind': 'raw-magnetic-acceleration-capture',
                      'clock': 'host-monotonic-receive', 'heading_qualified': False}:
            raise ValueError('Unexpected SSP broker capture header')
        for line in stream:
            yield json.loads(line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True,
                        help='Private SSP broker JSONL or pose JSON containing rows')
    parser.add_argument('--accel-matrix', type=matrix_arg, required=True)
    parser.add_argument('--magnetic-matrix', type=matrix_arg, required=True,
                        help='Explicit candidate, not inferred from acceleration or DT position number')
    parser.add_argument('--allow-low-accuracy-diagnostic', action='store_true')
    parser.add_argument('--reference-degrees', type=float)
    args = parser.parse_args()
    result = evaluate(capture_rows(args.capture), args.accel_matrix, args.magnetic_matrix,
                      1 if args.allow_low_accuracy_diagnostic else 2)
    if args.reference_degrees is not None:
        if not math.isfinite(args.reference_degrees) or not 0 <= args.reference_degrees < 360:
            parser.error('Reference must be a finite magnetic heading in0..360')
        if 'diagnostic_magnetic_heading_deg' in result:
            delta = math.radians(result['diagnostic_magnetic_heading_deg']-args.reference_degrees)
            result['reference_error_deg'] = math.degrees(math.atan2(math.sin(delta), math.cos(delta)))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

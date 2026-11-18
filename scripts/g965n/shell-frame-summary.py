#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Summarize shell-profile-marks TSV durations; this is NOT an FPS counter."""
import collections
import json
import statistics
import sys

marks = collections.defaultdict(list)
for line in sys.stdin:
    timestamp, duration, group, name = line.rstrip('\n').split('\t', 3)
    value = int(duration) / 1e6
    if value < 0:
        raise SystemExit('Negative mark duration; invalid capture')
    marks[(group, name)].append(value)
results = []
for (group, name), values in marks.items():
    values.sort()
    results.append({'group': group, 'name': name, 'count': len(values),
        'median_ms': round(statistics.median(values), 3),
        'p95_ms': round(values[int(.95*(len(values)-1))], 3),
        'max_ms': round(values[-1], 3)})
if not results:
    raise SystemExit('No marks; no performance conclusion')
print(json.dumps(sorted(results, key=lambda x: -x['max_ms']), indent=2))

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Summarize each transition separately; never mistake operation marks for FPS."""
import argparse
import json
from pathlib import Path
import statistics


def analyze(events, marks):
    grouped = {}
    for start, (mode, opening) in events:
        if not opening:
            continue
        if mode not in ('overview-first', 'app-grid', 'overview-repeat'):
            raise ValueError('Unexpected scene label')
        selected = [(ns, duration, name) for ns, duration, name in marks if start <= ns < start + 800_000_000]
        dispatch = sorted((ns, duration) for ns, duration, name in selected if name == 'Clutter::FrameClock::dispatch()')
        painted = [duration for _, duration, name in selected if name == 'Clutter::Stage::paint_view()']
        notified = sorted(ns for ns, _, name in selected if name == 'Clutter::FrameClock::presented()')
        if not dispatch or not painted or len(notified) < 2:
            raise ValueError('Incomplete opening capture')
        row = {'first_dispatch_ms': dispatch[0][1] / 1e6,
               'peak_dispatch_ms': max(d for _, d in dispatch) / 1e6,
               'median_dispatch_ms': statistics.median(d for _, d in dispatch) / 1e6,
               'peak_paint_ms': max(painted) / 1e6,
               'first_notification_after_input_ms': (notified[0] - start) / 1e6,
               'peak_notification_gap_ms': max(b-a for a, b in zip(notified, notified[1:])) / 1e6,
               'over_budget_dispatches': sum(d > 16_700_000 for _, d in dispatch),
               'dispatch_count': len(dispatch)}
        grouped.setdefault(mode, []).append(row)
    if set(grouped) != {'overview-first', 'app-grid', 'overview-repeat'} or any(len(rows) != 4 for rows in grouped.values()):
        raise ValueError('Need exactly four openings for each scene')
    return {mode: {'per_opening': rows,
                   'median_of_peaks_ms': round(statistics.median(r['peak_dispatch_ms'] for r in rows), 3),
                   'median_first_notification_ms': round(statistics.median(r['first_notification_after_input_ms'] for r in rows), 3),
                   'median_peak_notification_gap_ms': round(statistics.median(r['peak_notification_gap_ms'] for r in rows), 3),
                   'worst_dispatch_ms': round(max(r['peak_dispatch_ms'] for r in rows), 3)}
            for mode, rows in grouped.items()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events', type=Path, required=True)
    p.add_argument('--marks', type=Path, required=True)
    a = p.parse_args()
    marks = []
    for line in a.marks.read_text().splitlines():
        ns, duration, group, name = line.split('\t', 3)
        marks.append((int(ns), int(duration), name))
    events = json.loads(a.events.read_text())['events']
    print(json.dumps(analyze(events, marks), sort_keys=True))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('opening', Path(__file__).with_name('analyze-opening.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def scene(frames):
    events, marks = [], []
    for n, name in enumerate(('overview-first', 'app-grid', 'overview-repeat')):
        for cycle in range(4):
            start = (n*4+cycle+1)*2_000_000_000
            events.extend([(start, (name, True)), (start+1_000_000_000, (name, False))])
            for i in range(frames):
                ns = start+30_000_000+i*16_000_000
                marks.extend([(ns, 20_000_000 if not i else 1_000_000, 'Clutter::FrameClock::dispatch()'),
                              (ns+500, 500_000, 'Clutter::Stage::paint_view()'),
                              (ns+2_000_000, 1000, 'Clutter::FrameClock::presented()')])
    return events, marks


class OpeningTests(unittest.TestCase):
    def test_extra_fast_frame_cannot_fake_peak_improvement(self):
        a, b = (m.analyze(*scene(n)) for n in (15, 16))
        for mode in a:
            self.assertEqual(a[mode]['median_of_peaks_ms'], 20)
            self.assertEqual(b[mode]['median_of_peaks_ms'], 20)
            self.assertEqual(a[mode]['median_first_notification_ms'], 32)
            self.assertEqual(b[mode]['median_first_notification_ms'], 32)
            self.assertEqual(a[mode]['median_peak_notification_gap_ms'], 16)

    def test_missing_transition_rejected(self):
        events, marks = scene(15)
        with self.assertRaises(ValueError):
            m.analyze(events[2:], marks)

    def test_missing_notifications_rejected(self):
        events, marks = scene(15)
        with self.assertRaises(ValueError):
            m.analyze(events, [row for row in marks if 'presented' not in row[2]])


if __name__ == '__main__':
    unittest.main()

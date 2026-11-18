# SPDX-License-Identifier: GPL-2.0-only
import importlib.machinery
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'device/base/usr/local/libexec/g965n-screen-button'
loader = importlib.machinery.SourceFileLoader('screen_button', str(PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
button = importlib.util.module_from_spec(spec)
loader.exec_module(button)


class ShortPowerPressTests(unittest.TestCase):
    def feed(self, state, timestamp, value, code=button.KEY_POWER):
        return state.feed(timestamp, button.EV_KEY, code, value)

    def test_complete_short_press_toggles_once_on_release(self):
        state = button.ShortPress()
        self.assertFalse(self.feed(state, 10, 1))
        self.assertTrue(self.feed(state, 10.15, 0))
        self.assertFalse(self.feed(state, 10.16, 0))

    def test_repeat_or_duplicate_press_does_not_turn_a_long_hold_into_a_tap(self):
        for repeated_value in [1, 2]:
            state = button.ShortPress()
            self.feed(state, 10, 1)
            self.assertFalse(self.feed(state, 12, repeated_value))
            self.assertFalse(self.feed(state, 12.1, 0))

    def test_debounce_rejects_bounce_but_allows_a_later_new_press(self):
        state = button.ShortPress()
        self.feed(state, 10, 1)
        self.assertTrue(self.feed(state, 10.15, 0))
        self.feed(state, 10.2, 1)
        self.assertFalse(self.feed(state, 10.3, 0))
        self.feed(state, 10.8, 1)
        self.assertTrue(self.feed(state, 10.95, 0))

    def test_missing_press_glitch_or_negative_duration_never_toggles(self):
        state = button.ShortPress()
        self.assertFalse(self.feed(state, 10, 0))
        self.feed(state, 10.1, 1)
        self.assertFalse(self.feed(state, 10.11, 0))
        self.feed(state, 12, 1)
        self.assertFalse(self.feed(state, 11, 0))

    def test_other_buttons_are_not_matched_or_consumed(self):
        state = button.ShortPress()
        self.assertFalse(self.feed(state, 10, 1, code=115))
        self.assertFalse(self.feed(state, 10.1, 0, code=115))
        self.assertIsNone(state.pressed_at)

    def test_a_long_press_boundary_is_not_a_short_press(self):
        state = button.ShortPress()
        self.feed(state, 10, 1)
        self.assertFalse(self.feed(state, 11.5, 0))
        self.feed(state, 12, 1)
        self.assertTrue(self.feed(state, 12.1, 0))

    def test_other_keys_during_a_power_press_do_not_reset_its_duration(self):
        state = button.ShortPress()
        self.feed(state, 10, 1)
        self.feed(state, 12, 1, code=115)
        self.feed(state, 12.1, 0, code=115)
        self.assertFalse(self.feed(state, 12.2, 0))

    def test_dropped_event_stream_requires_a_fresh_complete_press(self):
        state = button.ShortPress()
        self.feed(state, 10, 1)
        state.feed(10.1, button.EV_SYN, button.SYN_DROPPED, 0)
        self.assertFalse(self.feed(state, 10.2, 1))
        state.feed(10.3, button.EV_SYN, button.SYN_REPORT, 0)
        self.assertFalse(self.feed(state, 10.4, 0))
        self.feed(state, 11, 1)
        self.assertTrue(self.feed(state, 11.15, 0))

    def test_display_modes_do_not_infer_support_from_unknown_values(self):
        self.assertEqual(button.next_power_mode(0), 3)
        for mode in [1, 2, 3]:
            self.assertEqual(button.next_power_mode(mode), 0)
        with self.assertRaises(ValueError):
            button.next_power_mode(-1)

    def test_model_guard_is_an_exact_compatible_entry(self):
        self.assertTrue(button.is_star2lte(b'samsung,star2lte\0samsung,exynos9810\0'))
        self.assertFalse(button.is_star2lte(b'samsung,star2lte-other\0'))

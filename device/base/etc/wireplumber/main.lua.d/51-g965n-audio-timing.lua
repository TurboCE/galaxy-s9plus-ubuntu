-- SPDX-License-Identifier: GPL-2.0-only
-- WirePlumber 0.4: bounded spoken recording/replay passed on G965N kernel#11.
-- This rule matches only the opt-in ABOX prototype, not other audio devices.
table.insert(alsa_monitor.rules, {
  matches = {
    { { "node.name", "matches", "alsa_output.platform-snd-zrn-abox.*" } },
    { { "node.name", "matches", "alsa_input.platform-snd-zrn-abox.*" } },
  },
  apply_properties = {
    ["api.alsa.period-size"] = 1024,
    ["api.alsa.headroom"] = 1024,
    ["api.alsa.disable-mmap"] = true,
  },
})

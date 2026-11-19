# Exynos9810 dual CLKOUT source candidate

This standalone source change implements the missing Exynos9810 CLKOUT provider.
It has host fake-MMIO/cleanup tests and source cross-checks, not a device boot or
clock-function qualification. It does not connect or enable audio/NFC consumers,
change their policy, access a device, or alter a bootloader/protected partition.

## Hardware facts and mapping

The owner's pinned Lineage source commit is
`6a9461f9460ca51d1217e5069a5d5556fcc79e63`.
`drivers/soc/samsung/cal-if/exynos9810/clkout_exynos9810.c` defines:

| Provider ID | Physical output | PMU offset | Mux width / shift | Known TCXO selector | Stock consumer |
| --- | --- | --- | --- | --- | --- |
| 0 | CLKOUT0 | `0xa00` | 6 / 8 | 1 | `OSC_AUD`, sound `xclkout` |
| 1 | CLKOUT1 | `0xa0c` | 6 / 8 | 0 | `OSC_NFC`, NFC `oscclk_nfc` |

Both gates use bit 0. `cal-if/ra.c:ra_enable_clkout` selects the mux then clears
bit 0 to enable, and sets bit 0 to disable. This matches mainline's existing
`CLK_GATE_SET_TO_DISABLE`, not an inverted guess.

`drivers/clk/samsung/clk-exynos9810.c` maps OSC_AUD to CLKOUT0 and OSC_NFC to
CLKOUT1. `include/dt-bindings/clock/exynos9810.h` assigns those stock CMU IDs 921
and 920, respectively. The pinned rev26 board DTS connects sound `xclkout` to
921 and NFC `oscclk_nfc` to 920. The existing port board describes `oscclk` as
26 MHz, and the stock audio FLL reference is also 26 MHz. These facts identify
the TCXO parent; they do not identify every other hardware mux input.

## Scope and compatibility

The old provider supports one register/output and up to 32 named mux inputs.
Adding an Exynos5433-compatible alias would describe the wrong hardware and
still leave the new PMU without parent clocks. The patch instead uses an early
Exynos9810-specific branch in probe/remove/suspend/resume. After removing that
branch and its new implementation block, the original driver is byte-identical:
existing compatible tables, one-output IDs, flags and APIs are unchanged.

The new branch registers two composites with six-bit muxes and inverted gates.
Each output has a 64-slot parent map; only its known TCXO slot is associated
with a real clock. All other slots remain named orphans, so a currently unknown
hardware selection is not misreported as a known TCXO input. No unknown clock
source or frequency is invented. Both registers share the driver's spinlock.

The SoC PMU DT receives `#clock-cells = <1>`, two references to `oscclk`, and
existing-schema names `clkout0` and `clkout1`. Here the names label known mux
input slots: input 0 is known for NFC and input 1 for audio. They are not a
claim that both inputs are valid on both outputs. Provider IDs refer to physical
outputs as shown above. Existing audio/NFC DT nodes are not changed to consume
the new provider.

Exynos9810 alone uses `CLK_IGNORE_UNUSED`: until consumers are integrated,
clock cleanup must not gate bootloader-inherited outputs just because Linux
has no consumer reference. Probe does not set a mux, enable or disable a clock.
The existing unrelated variants do not gain this flag. Future consumer policy
needs separate review; do not use this candidate to change a live audio/NFC
clock silently.

A failed second registration unregisters the first. A provider-registration
failure unregisters both, in reverse order. Every failure after mapping unmaps
registers; every acquired parent reference is released. Successful removal
removes the provider, unregisters both clocks, unmaps and releases both parent
references. Suspend captures both full register values under the lock; resume
restores both under the same lock. This retains bits outside the mux/gate masks
rather than constructing a replacement register value from incomplete facts.

## Applying and reproducing source checks

`SOURCES.json` pins the exact original/patched driver and SoC DTS hashes, patch
hashes, and the generic gate/mux source hashes used by the C test. The reviewed
Linux source commit is `8cd9520d35a6c38db6567e97dd93b1f11f185dc6`.

```sh
python3 experiments/clkout/apply.py check --kernel-source KERNEL_SOURCE
python3 experiments/clkout/apply.py apply --kernel-source KERNEL_SOURCE
```

The helper verifies both inputs before edits, dry-runs both patches, uses zero
fuzz and rejects unknown drift. Exact patched inputs are accepted on rerun.
It does not build, flash, install, enable, load or query hardware. The reviewed shared build stage invokes this source-only recipe before compilation.

The original Samsung copyright, author and GPL-2.0-only notices are retained in
the driver. The SoC DTS retains its original GPL-2.0/BSD-3-Clause notice and
upstream authors. New additions/helper/tests are GPL-2.0-only. Full original
sources remain at their pinned upstream commits; no firmware, raw logs,
identifiers, native config or backups are included here.

```sh
python3 experiments/clkout/test_correctness.py
```

Set `CLKOUT_FIXTURE` to private pristine copies of `clk-exynos-clkout.c`,
`exynos9810.dtsi`, `clk-gate.c` and `clk-mux.c`.
`LINEAGE_KERNEL_SOURCE` optionally enables an independent read-only Git
extraction of the exact vendor definitions/stock consumers.

The host harness compiles the actual new C provider and the actual upstream
`clk_gate_endisable`/`clk_mux_set_parent` functions with ASan/UBSan, substituting
fake allocation, registration and MMIO backends. It checks both offsets, all
64 parent slots, six-bit selection boundaries, gate polarity, preserved other
register bits, no probe writes in that harness, dual suspend/restore and eight
partial-failure cleanup cases. This tests the real provider/control functions;
it does not replace a native build or prove every clock-framework side effect.
A separate exact-source comparison verifies unchanged old variants and the
minimal DT additions. Native #24 registers both outputs without the former parent/probe errors.
Output1 reports a known26MHz parent and is disabled; output0 remains enabled
with an unknown parent/rate0. Its inherited mux was deliberately preserved.
No hardware output/suspend/audio/NFC clock qualification follows from provider
registration or host tests; no new consumer is attached.

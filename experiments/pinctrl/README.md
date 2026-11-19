# Exynos9810 pinctrl interrupt topology corrections

These source candidates address three boot diagnostics without changing the
messages or removing DT nodes. They have host regression checks, not a hardware
boot qualification. They are not part of the already built #22 image.

## Causes and changes

ALIVE and CMGP contain only wakeup (`EINTW`) or non-interrupt (`EINTN`) banks.
Their controller data nevertheless requests the separate generic GPIO-group
(`EINTG`) initializer. That initializer requests a controller-level aggregate
IRQ before checking bank types; the mainline DT correctly has no such aggregate
GPIO IRQ for these two controllers. Remove only their `eint_gpio_init` callback
assignments. Retain both wakeup initializers, every pin bank, suspend/resume
callbacks and all other controller entries. No IRQ, device or bank is disabled.

The old vendor data also assigned those callbacks, but its DT duplicated
individual wakeup IRQs at the controller level. Copying its controller IRQ list
into mainline would attach a generic GPIO-group handler to an individual wakeup
line; that is not the mainline topology and is not the proposed fix.

Separately, `gpa4` is a two-pin wakeup bank. Mainline omits its individual parent
interrupts, so `exynos_eint_wkup_init` misclassifies it as a muxed wakeup bank and
then cannot find a mux-parent IRQ. The owner's pinned Lineage rev26 DTS describes
its two pins in this exact order:

- pin 0 → GIC SPI 446 (`0x1be`);
- pin 1 → GIC SPI 447 (`0x1bf`).

Add those two parent interrupts with explicit `interrupt-parent = <&gic>` and the
same level-high parent convention used by the existing mainline `gpa0`–`gpa3`
wakeup banks. The vendor DTS uses unspecified zero trigger flags, not a claim
that the electrical interrupt is edge-triggered. Do not copy its legacy
three-cell GPIO binding or zero GIC trigger flags. No aggregate/mux IRQ number is
invented, and all consumers and other banks remain unchanged.

## Reproduction and guards

`SOURCES.json` pins exact before/after SHA-256s for the two kernel sources and
patch hashes. Upstream source reference:
`8cd9520d35a6c38db6567e97dd93b1f11f185dc6`.
IRQ and pin-order reference:
`LineageOS/android_kernel_samsung_exynos9810` commit
`6a9461f9460ca51d1217e5069a5d5556fcc79e63`,
`arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts`, `gpa4` node;
its pinctrl implementation also identifies `gpa4` as a two-pin wakeup bank.

```sh
python3 experiments/pinctrl/apply.py check --kernel-source KERNEL_SOURCE
python3 experiments/pinctrl/apply.py apply --kernel-source KERNEL_SOURCE
```

The helper verifies all source identities and dry-runs both patches before any
edit, rejects drift, applies without fuzz and accepts only exact patched output
on rerun. It never builds, installs, flashes or accesses a device. The shared build patch stage invokes it after review, before kernel compilation.

Existing Samsung copyright and GPL-2.0-or-later source notices are preserved.
The DTS retains its GPL-2.0/BSD-3-Clause dual notice and named upstream authors.
New patch additions, helper and regression code are supplied GPL-2.0-only; the
complete original sources and notices remain in their upstream trees. No
firmware, raw device log, private identifier or backup is included.

## Host validation and hardware limits

```sh
python3 experiments/pinctrl/test_correctness.py
```

Use `PINCTRL_FIXTURE` for private copies of the two exact original source files.
`LINEAGE_KERNEL_SOURCE` optionally supplies the pinned Lineage Git tree for an
independent read-only extraction of the six original GIC cells. The tests apply
patches only to temporary copies, verify exact identities/idempotence/refusal of
foreign drift, preserve original source notices and bytes outside the intended
edits, and compile the actual original/patched Exynos9810 bank/controller data
with ASan/UBSan. Original data invokes two erroneous GPIO-group initializers;
patched data invokes zero while retaining both wakeup callbacks and all banks.
No native kernel object or image is built.

A later boot must confirm the two missing-controller-IRQ diagnostics and the
missing-mux diagnostic disappear, with no new pinctrl/IRQ errors. No button,
touch, fingerprint, sensor or wake-from-suspend functionality is claimed from
these source tests. Do not run feature exercises as part of this log-only work.

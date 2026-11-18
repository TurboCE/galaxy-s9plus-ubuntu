# MAX77705 functional wiring and source review

Status: source-only candidates; RGB and haptics remain **UNVERIFIED**. No device
access, driver enable, configuration/DT change, kernel build or flash is part
of this review. The existing separate charger is not replaced or reconfigured.

## Evidence and register banks

The clean cached kernel commit is
`8cd9520d35a6c38db6567e97dd93b1f11f185dc6`. Relevant sources are
`drivers/mfd/max77705.c`, `drivers/leds/leds-max77705.c`,
`drivers/input/misc/max77693-haptic.c`,
`include/linux/mfd/max77705-private.h`, and
`Documentation/devicetree/bindings/mfd/maxim,max77705.yaml`.

Lineage reference commit
`6a9461f9460ca51d1217e5069a5d5556fcc79e63` supplies independent primary evidence
in `drivers/motor/max77705_haptic.c`, `drivers/leds/leds-max77705-rgb.c`,
`drivers/mfd/max77705.c`, `include/linux/mfd/max77705-private.h`, and
`arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts`.
The privately extracted owner rev26 DT agrees on the relevant wiring; no
private image, identifiers or logs are redistributed here.

| Function | Verified source layout | Remaining wiring issue |
| --- | --- | --- |
| Charger | Separate I2C address 0x69, own I2C driver, interrupt index0 from PMIC | Preserve the current node; the MFD's charger platform cell has no matching platform driver/child binding |
| Fuel gauge | Separate I2C address 0x36, interrupt index2 | Preserve the existing device |
| RGB | Top PMIC I2C0x66, registers0x30..0x36 | Needs a real `leds` child and driver configuration after source/binding review |
| Haptic | Top PMIC I2C0x66, MAINCTRL1=0x02 bit7 BIASEN, MCONFIG=0x10 | Needs PWM, real motor supply, configuration and controlled hardware verification |

The RGB reference driver's probe explicitly uses `max77705_dev->i2c`. The old
header's separate RGB slave-address comment is not a basis for moving it to
another I2C address. The cached LED regmap adds base0x30 to its relative offsets.

The haptic variant already uses the parent's top-PMIC regmap and LRA/external
PWM mode. Both the pinned MAX77705 header and Lineage initialization establish
MAINCTRL1 bit7 as its bias control. MAX77843 also uses address0x02/bit7, but its
existing branch and normal behavior are retained separately.

## Candidate patches and host checks

The reproducible patches and exact before/after/patch hashes are under
`experiments/pmic/`. Original source copyright and license headers are retained.
The haptic file remains GPL-2.0-or-later; the LED file retains its GPL-2.0 notice.
Our additions/helpers/tests are provided under GPL-2.0-only.

The RGB candidate:

- Passes the registered multicolor `led_classdev` to initial-off, instead of
  the unrelated single-color member.
- Uses separate thin single/multicolor blink wrappers to derive the correct
  containing object and preserves the existing shared timer encoding.
- Supplies LEDEN's two-bit mask before its ON value, preserving other channels.
- Returns a failed child parse before registration or register writes, and
  preserves the first register-update failure instead of continuing a group.

The haptic candidate supports the verified MAX77705 BIASEN address/bit. A failed
bias-enable stops before supply enable. A failed supply enable clears bias once
for MAX77705 and returns the original supply error even if that cleanup also
fails. The secondary cleanup error is still logged. Existing MAX77843 failure
policy is unchanged; other variants do not receive new bias writes.

The host test compiles actual patched C functions and injects API failures.
It checks correct single/multicolor object pointers, initial-off and blink
callbacks, channel-neighbor preservation, parse/registration/write failure
propagation, MAX77705/MAX77843 register/bit behavior, other-variant exclusion,
and first-error-preserving supply unwind. It also checks repeat application and
refusal of source drift. These are software checks, not PMIC transactions or
proof of light/vibration output.

## Blockers before functional enablement

The examined configuration has `INPUT_MISC` disabled and `LEDS_MAX77705`
disabled. `PWM_SAMSUNG` alone does not supply the missing haptic connection.
No DT/config change is included in these candidates.

The owner/reference DT specifies PWM at0x10510000, channel1, `gpp3-1` function2,
motor-boost enable on `gpg1-7`, the supply name `VDD_MOTOR_3P3`, and a first
period48828ns. The current mainline SoC DT lacks that PWM clock connection.
Mainline's PWM driver requires clock name `timers`; the vendor DT's
`pwm_pclk`/`pwm_sclk` IDs cannot be copied into a different clock provider.
Prove the real gate/rate and compatible/binding requirements before adding a
PWM node. A fabricated clock or dummy supply is not a functional port.

The multicolor LED binding example lacks a parent `reg`, but the examined
driver requires it. Resolve that discrepancy rather than guessing a DT property.
The existing blink callback only changes a shared timer register; these patches
do not establish per-channel/group blink-mode control or timing equivalence.
Optional color handling and the longer delay ranges need separate review.

Lineage applies panel/color-specific current ratios. The cached driver's
brightness255 maximum is not proof of an appropriate current limit for this
phone. Likewise generic FF_RUMBLE does not reproduce the stock seven frequency
profiles or its normal/overdrive duty limits. Determine supported limits and
test conservative bounded output before making user-facing feature claims.

Removing orphan MFD cells or hiding their missing-node warnings would not
resolve these functional blockers. The charger cell is deliberately unchanged
until a separate integration review determines the correct model.

# Samsung charging policy parity — incomplete

This is a source candidate and gap analysis, **not Android-equivalent charging
on the handset**. No new charger driver, module or kernel has been installed.
The owner's earlier one-time auto restoration is separate from this work.

## Reference and ownership

`REFERENCE.json` pins public Samsung/LineageOS source, commit, tree and file
hashes. Original Samsung GPLv2 notices remain upstream. The source change in
`src/soc/max77705_charger.c` retains the original upstream copyright and GPL
notice; our additions/tests are GPL-2.0-only. No extracted firmware, private DT,
raw logs, identity, battery history or private receipts are included.

Read the pinned `drivers/battery_v2/sec_battery.c`, `sec_adc.c`,
`max77705_charger.c` and board DTS from that repository/commit. The lower
charger accepts a CHARGING_ENABLED mode and retains `is_charging`; sec-battery
selects that mode. It is not a periodic unconditional CHG=1 implementation.

## Current implementation and missing work

| Path | Android reference | Native port / candidate |
|---|---|---|
| Charge intent vs actual state | `charge_mode`/`is_charging` distinct from CHG register | Candidate records accepted intent with serialization; separate read-only actual and requested attributes. No auto-recovery yet. |
| Manual inhibit | Explicit charge mode OFF | Existing inhibit ABI preserved. Candidate keeps last accepted intent; failed I/O cannot change it. |
| Before probe completes | Initialization precedes normal policy | Candidate rejects charge requests with EAGAIN until initialization finishes, preventing accepted inhibit being silently overwritten by startup. |
| Input attach/detach | Cable work selects charge policy/current | Native CHGIN work currently only notifies power_supply. Full cable-policy integration missing. |
| Temperature | Dedicated battery/USB/charger ADC sources, hysteresis, swelling policy | Fuel-gauge temperature and SSP board thermistors exist, but they are not substitutes for these calibrated channels. Not connected. |
| Full/recharge | Charge-complete detection, full and recharge state/counters, temperature-dependent thresholds | Native hardware status available, equivalent upper policy missing. |
| Charger protection/reset | Unlock/readback/init and conditional fault handling | Equivalent qualified recovery absent. Do not blindly unlock/reinitialize or set CHG periodically. |
| Runtime safety time/current | Cable/current-dependent timing, abnormal-voltage and battery protection | Equivalent upper policy missing; retain current input/current/CV limits. |

The candidate adds `charge_requested` and `charge_enabled` under the I2C
charger device (`.../power_supply/max77705-charger/device/`). They report 0/1:
accepted control intent vs actual CNFG_00 CHG readback. Existing charge_behaviour
continues to report hardware enable/inhibit, so no existing ABI meaning changes.
Requests touch only the already qualified CHG bit. Manual inhibit remains
explicit. The diagnostic attributes cannot enable charging, and no timer,
thermal bypass or automatic re-enable loop is added. Intent is per boot, not
persistent across shutdown. Cleanup still uses the original disable action.

## Reference thresholds — not live setpoints

The public EUR rev26 DT uses battery/USB ADC source2, check count1,
battery high50C/recover45C, low0C/recover5C, USB high-limit80C/recover75C.
Separate swelling policy starts at41C/recover39C, with additional cold limits,
current/voltage restrictions and recharge conditions. Normal recharge uses
VCELL <=4280mV (type4), not simply SOC<=98; full-condition configuration and
swelling state also gate it. These are reference values, not verified policy
for the owner's Korean firmware. Nothing has programmed them into hardware.

Its ADC provider is `samsung,exynos-adc-v3` at0x14230000; named inputs are
adc-temp=channel4, adc-chg-temp=3, adc-in-bat=11, adc-wpc-temp=4,
adc-usb-temp=1. This provider is absent from the native board description.
Bring up its real clock/reset/IRQ, IIO channels, calibrated conversion and
sample validity first. Do not substitute SSP thermistor channels, fuel-gauge
temperature, zero/missing values or guessed thermal thresholds.

## Validation and build-only reproduction

Run `python3 -m unittest discover -s tests -p test_charger_properties.py -v`.
The harness compiles the actual production C request/property helpers with a
faultable regmap. It checks unexpected hardware-bit loss while intent stays
ON, manual inhibit, failed writes preserving intent, startup rejection and
unchanged neighboring bits. Existing current, AICL-minimum, health/status,
I/O and exact-source migration tests remain. Eight tests pass; migration from
the previous qualified source hash was separately exercised successfully.

Compile against the reviewed configured mainline kernel source/output tree:

```sh
# Use a new private output directory. This builds only, never flashes/loads.
mkdir "$CANDIDATE_OUT"
cp src/soc/max77705_charger.c "$CANDIDATE_OUT/g965n-charge-candidate.c"
printf 'obj-m += g965n-charge-candidate.o\n' > "$CANDIDATE_OUT/Makefile"
make -C "$KERNEL_SOURCE" O="$KERNEL_OUT" M="$CANDIDATE_OUT" \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- g965n-charge-candidate.o
```

Actual ARM64 C-object compilation passed against the configured v7.1 tree.
The first compile used an unavailable devm_device_add_groups API; corrected to
the supported singular devm_device_add_group. A full external-module attempt
failed modpost because that output lacks qualified Module.symvers. No warning
bypass or fabricated exports were used. Object compilation is not successful
module linkage, full kernel build, a hardware boot, or charging-policy parity.
Never load an alternate I2C charger driver over the live driver or rebind the
PMIC to trial it. A future qualified BOOT trial needs adequate battery, exact
model/BOOT/protected-backup checks, preserved original image/receipts and the
normal guarded installation route.

Read-only2026-11-23 follow-up: battery0%/22C/3.314V, average+63mA,
Charging/auto. The sensor unit failed this boot before child readiness and
root IIO inventory was empty. No sensor restart/reset was attempted while the
battery is depleted. This is an additional unavailable-temperature dependency,
not a reason to guess temperatures or enable an unconditional charge loop.

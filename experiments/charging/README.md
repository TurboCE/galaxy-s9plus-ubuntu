# Samsung charging policy parity — incomplete

This is a source candidate and gap analysis, **not Android-equivalent charging
on the handset**. Bounded ADC diagnostics and a read-only charger snapshot
were loaded and removed on native #48; no replacement charger driver or
new kernel has been installed.
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
| Temperature | Dedicated battery/USB/charger ADC sources, hysteresis, swelling policy | ADC channels 4/1/3 read successfully in a bounded trial; public calibration matches owner wired tables. Persistent fresh thermal service and upper charging policy still missing; fuel-gauge/SSP values are not substitutes. |
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
swelling state also gate it. The wired battery/USB/charger calibration and relevant protection/full/recharge
fields match the owner's original rev26 firmware variants in a read-only
comparison. One wireless LCD-on field differs in one variant; wireless policy
is not qualified. These references have not been programmed into hardware.

Its ADC provider is `samsung,exynos-adc-v3` at0x14230000; named inputs are
adc-temp=channel4, adc-chg-temp=3, adc-in-bat=11, adc-wpc-temp=4,
adc-usb-temp=1. This provider is absent from the native board description.
The opt-in diagnostic now verifies inherited gate readiness, performs ADC v3
reset/conversion with IRQ completion and restores controls. It does not own
clock gate/rate policy; production clock/runtime power management and a
persistent calibrated thermal consumer remain to implement. Do not substitute SSP thermistor channels, fuel-gauge
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


## 2026-11-23 hardware-qualified diagnostic path

`g965n-adc-v3.c` implements the vendor v3 register sequence (DATA at 0x08,
reset then non-reset, CTIME6, 12-bit samples, 100ms completion timeout).
`g965n-adc-board.c` requires the observed firmware-held ADC access gates and
an unowned SPI8 mapping. Its CCF handle only checks readiness; it neither
programs CMU/PLL nor supplies an invented rate. This limited wiring must not
be mistaken for a complete runtime-PM/suspend implementation.

`adc-trial.py` requires the existing exact SM-G965N/#48/BOOT/protected-backup
preflight, root-only package pins, qualified export ABI, at least 5%/3.5V,
external power and bounded fuel-gauge prerequisites. These prerequisites only
permit diagnostics; the gauge reading does not qualify physical temperature.
The first trial refused a charger fault; allowing **diagnostic-only** sampling
during that fault subsequently succeeded. No protection was bypassed to charge.
Five rows of channels 4/1/3/11 completed; both ADC modules were removed, ADC
controls/gate observations/IRQ type matched the pretrial snapshots. No service,
auto-enable loop, charger limits or firmware were installed/changed.

`temperature.py` converts the private five-row receipt for channels 4/1/3
using the pinned public tables, trimmed mean and Samsung C signed-division
rounding. Out-of-range samples, missing samples, non-monotonic captures and
captures longer than five seconds are rejected, including invalid outliers.
A completed receipt is historical evidence, **not a fresh thermal-policy input**.
One capture gave battery 37.7C / USB 35.5C / charger 39.9C, while the gauge
reported 22C. Android also writes externally measured temperature into its
fuel gauge; the native gauge reading alone cannot qualify these thermistors.
Channel 11 remains raw: no guessed voltage-divider conversion.

`g965n-charge-snapshot.c` reads only non-clearing status/configuration through
the bound owner's regmap, then is removed. It never reads IRQ-clear status or
writes configuration. Actual CHG_DTLS=6, BAT_DTLS=2, CHGIN_DTLS=3, CHG_EN=1,
CHGPROT=0 and WDTEN=0 were observed. Native health reports Dead, but this is
not proof of a permanently failed battery. Exact Samsung source reports
NotCharging for this charge state; its qualified conditional recovery handles
states 8/11, not this state. Related-chip timer-fault descriptions are not an
exact MAX77705 qualification. CHGPROT=0 alone does not prove a chip reset.
No speculative reset/unlock/reinitialization has been performed.

Before reattach: 8%, about 3.64V, USB online, auto/NotCharging and average
near-zero net discharge. The owner then disconnected/reconnected USB for ten
seconds: Charging/Good returned, battery net current reached +80..122mA,
average rose to +34mA and voltage reached about 3.67V. The same read-only
snapshot now showed CHG_DTLS=1 / BAT_DTLS=4 / CHGIN_DTLS=3, with CHG_EN=1,
CHGPROT=0 and the input code unchanged. The diagnostic module was removed.
This demonstrates physical input reattachment cleared this occurrence; it
does not identify what originally caused the fault or qualify a software
reset sequence. CHGPROT=0 also exists while charging normally, so lock state
alone cannot diagnose the fault. Sustained charging is **not yet qualified**. Do not shut down a low-battery phone: cold USB autoboot
is not supported. Persistent calibrated thermal policy, fault recovery,
full/recharge, long-duration charging and reboot qualification remain open.

Build all three diagnostic modules without device access:

```sh
KERNEL_SOURCE=/reviewed/kernel/source KERNEL_OUT=/qualified/kernel/out \
DIAGNOSTIC_OUT=/new/private/output experiments/charging/build-diagnostics.sh
python3 -m unittest discover -s tests -p 'test_charging*.py' -v
```

The builder rejects a mismatching Module.symvers hash and requires a new
output directory. The qualified #48 export ABI is inherited from its reviewed
#47 base (RTC-only incremental #48 build); an unrelated configured output's
missing Module.symvers was the initial modpost failure. Correct qualified
output subsequently passed compilation, modpost and linkage of all three
modules. No warning bypass. Source availability and matching exports are
necessary, not sufficient to authorize loading on another kernel/device.
The initial board build's unavailable of_node_to_fwnode was corrected to
of_fwnode_handle. Host tests exercise actual driver conversion/IRQ/error paths
with ASan/UBSan and compare every calibration interval with C arithmetic.

Public source is GPL-2.0-only with the ADC author's original GPL2-or-later
notice preserved and version 2 elected. Builds/receipts/stock firmware are
private and excluded from Git. Diagnostic installation must use the existing
model/BOOT/backup guards and newly generated root-only package pins; this
builder intentionally performs no installation or flashing.

## Continuous diagnosis — 2026-11-23

See [CAUSES.md](CAUSES.md) for evidence, candidates and how to distinguish them.
The current live IC CNFG_01=0x91 does not match the native initializer's intended
fast-timer/restart/prequalification fields0/3/0. That difference is observed;
ignored initialization vs a later reset/write is not yet distinguished.
Do not unlock and replay initialization blindly: that could disable hardware
safety timers before equivalent upper software protection exists.

The owner-authorized recorder is **installed, active and enabled on #48**:
`g965n-charge-observer.service`. No new BOOT/charger driver was installed.
It uses the qualified raw ADC modules and revised root-read-only live snapshot
module. Each snapshot parameter now reads the owner's regmap, not an old
module-load value. It exposes12 non-clearing status/config registers and
never reads IRQ acknowledgement status. Reads are bracketed by monotonic time,
not claimed to be an atomic hardware snapshot.

Every15seconds it records:

- Actual charge behaviour/status/health, battery voltage/current/average/SOC,
  input/charge limits and available fuel-gauge temperature.
- IC state and configuration, decoded fields and intended-init differences.
- Five raw ADC rows and calibrated battery/USB/charger temperatures; failures
  remain errors. `thermal-policy.py` adds stock normal hot/cold/USB hysteresis
  and a distinct swelling-high-temperature flag **in shadow mode only**.
  These are not complete swelling, cold-current, full/recharge or safety-time
  policies, and no resulting recommendation controls the charger.
- Filtered kernel messages from an independent nonblocking `/dev/kmsg` reader.
  Bounded draining includes available boot messages; old overwritten messages
  cannot be recovered. Private files are fsync'd per record and rotate4x4MiB.

`audit-controls.py` installs only its own three write watches after the model/
BOOT/backup guard and device discovery. It does not delete other audit rules,
enable global audit or change immutable audit policy. Standard Ubuntu auditd
and libauparse were installed from official ARM64 packages, verified against
APT metadata SHA256, after an on-device network download timed out. Auditd
installation enabled standard kernel auditing; its logging retention was set
to4MiB/3files, and its previous config is privately backed up. `dpkg --audit`
was clean. No package or private log is distributed by this repository.

Actual watches cover charge_behaviour, constant_charge_current and
input_current_limit. A safe **open-for-write with no bytes written** proved
file/process syscall attribution while control readback stayed unchanged.
A separate temporary regular-file probe was removed afterward. Default
ausearch invocation initially returned no matches; explicit `-if` input
successfully found the actual syscall/process/path records. Inspect with:

```sh
sudo systemctl status g965n-charge-observer.service
sudo ausearch -if /var/log/audit/audit.log -k g965n_charge_control --raw
# Raw samples/boot IDs/receipts are private; do not upload or commit them.
sudo tail -n 1 /var/lib/g965n-charge-observer/samples.jsonl
```

Audit attributes userspace file access, not kernel-internal register writes,
and does not record the complete text buffer accepted by every sysfs write.
Fifteen-second register sampling cannot capture every transient. Current #48
has no KPROBES/FTRACE. The candidate driver adds request/result/actual-bit and
caller logs, devres-disable attribution and before/after/error init snapshots;
these need a new qualified kernel trial. It also rejects silent CHG readback
mismatch and propagates an ignored float-voltage setup error. ARM64 candidate
object compilation and faultable C tests pass, but it is **not installed**.

Actual recorder checks: one-shot start/sample/stop, module removal and control/
clock/IRQ restoration passed; service stop/restart and fresh samples passed.
At38records no temperature errors occurred; battery rose to15%, Charging/Good.
Temperatures were about38.3/36.1/40.6C, without changing charger limits.
Boot enablement is configured; actual next-reboot/suspend, long-duration fault
capture, full/recharge and enforcement of Android-equivalent policy remain
unverified/incomplete. Startup refuses unqualified BOOT/ABI, existing module
owners, insufficient stable battery or changed script/module hashes.

The root-only install directory additionally needs `charge-observer.py`,
`temperature.py`, `thermal-policy.py`, `audit-controls.py`, `adc-trial.py`,
three qualified modules and `observer-pins.json` containing their SHA256s,
module export ABI and scripts. Preserve prior files/private receipts and run
the existing exact-model/BOOT/protected-backup guard before installing.
The service starts after auditd and re-establishes its owned watches after
normal device discovery; it never adds broad syscall rules or `auditctl -D`.

To stop only this experiment (the normal charger remains bound):

```sh
sudo systemctl disable --now g965n-charge-observer.service
```

Owned ADC/snapshot modules are removed and before/after state is recorded.
The audit watches deliberately remain until explicitly removed using their
exact paths/key; do not globally disable audit or erase unrelated rules.
No reboot, firmware, current/CV change or unconditional charge-enable loop
was used for this installation.

Additional verified policy gap: all three owner rev26 original wired targets
are4350mV, while native battery DT set constant-charge-voltage-max to4400mV
and init used battery design voltage. The candidate keeps the descriptive
4.4V design rating but changes the charge ceiling to4.35V, uses the charge
ceiling bounded by design rating, preserves4.2V fallback when policy is absent,
rejects unsupported targets and propagates programming errors. Faultable C
tests and ARM64 object compilation pass. This source/DT change is not yet
installed; live CV remains4.2V. No observed overvoltage incident is claimed.

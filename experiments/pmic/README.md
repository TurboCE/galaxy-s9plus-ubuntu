# MAX77705 source correctness candidates

These three patches are **source correctness candidates**. They do not add
DT nodes, change kernel configuration, enable a driver, write a PMIC register,
build a kernel, or install anything.

`SOURCES.json` pins the clean cached kernel commit, all input and output file
hashes, and each patch hash. It preserves the upstream GPL-2.0 LED notice and
GPL-2.0-or-later haptic notice. Patch additions, application helper and tests
are GPL-2.0-only; the original source notices are unchanged. In particular the
haptic source retains Samsung's 2014/2015 copyright and both named authors.

Check/apply only to a separately prepared source checkout after review:

```sh
python3 experiments/pmic/apply.py check --kernel-source /path/to/kernel
python3 experiments/pmic/apply.py apply --kernel-source /path/to/kernel
python3 experiments/pmic/test_correctness.py --kernel-source /path/to/kernel
```

The helper checks every input before any patch is applied, dry-runs with zero
fuzz, verifies the output hashes, and treats an already patched file as a no-op.
An unknown source/patch hash is an error, not a reason to force an application.
If applying fails, preserve the checkout for review. The tests copy the three
patched source files to a temporary tree; they do not change the supplied checkout.
They compile actual patched production C functions with faultable regmap,
registration and regulator stubs, not an independent model of those functions.

The RGB changes correct object identity for multicolor initial-off and blink
callbacks, fix LEDEN mask/value order, and propagate parse/register errors.
The haptic changes add MAX77705's verified bias register/bit and roll it back
after a failed motor-supply enable for this variant only. A rollback write
failure remains a logged failure; it does not establish that the rail is off.

Binding ambiguity for the multicolor parent's `reg`, LED current/color limits,
blink mode/timing behavior, PWM clock wiring, motor supply validation and stock
waveform parity remain outside these patches. Do not add DT nodes or advertise
RGB/vibration support solely because these C tests pass. See
[`PMIC_REVIEW.md`](../../docs/g965n/PMIC_REVIEW.md) for the evidence and limits.

## Remove a phantom charger platform cell

Patch 0003 removes exactly one MFD registration-array entry for a platform child
named `max77705-charger`. The charger is a separately addressed I2C device;
`drivers/power/supply/max77705_charger.c` registers an `i2c_driver`, not a platform
driver. Its binding `power/supply/maxim,max77705.yaml` requires `reg` and shows
`charger@69` directly below an I2C controller. The PMIC MFD binding describes RGB
and haptic children, not a charger platform child. An MFD platform cell neither
creates that I2C client nor connects to the I2C driver.

The real `charger@69` DT node, monitored battery, charger/fuel-gauge links and
PMIC interrupt controller remain unchanged. The real charger receives PMIC IRQ
index 0 through that controller's existing regmap IRQ domain; removing the
unused platform cell does not remove that domain or its charger source bit.
The RGB and haptic platform cells remain exactly as before, including their
unresolved board-node warnings. No empty/disabled child DT node or warning
filter is added. This is a device-bus topology correction, not evidence of a
new charging, RGB or vibration capability.

The third regression compiles the actual original and patched MFD registration
arrays and original PMIC IRQ array with ASan/UBSan. It checks the change from
three cells to the two unchanged RGB/haptic cells, unchanged cell resources,
unchanged four interrupt-source masks and unchanged IRQ-domain registration
code. It also pins the actual I2C charger source and tracked board DTS hashes,
asserts that I2C driver registration and `charger@69` address/IRQ/battery
properties remain intact, and proves the complete MFD source differs by only
that one deleted line. Updated tests accept all three sources through the same
exact-hash patch recipe. A later native boot must verify the phantom charger
warning disappears while the real I2C charger and supplies still bind; host
checks do not establish that hardware outcome.

Original MFD GPL-2.0-or-later SPDX and Dzmitry Sankouski copyright are preserved.
The third patch does not alter the I2C charger driver, schema, DT or register
settings. No raw boot log or firmware is published. Package pins in `SOURCES.json` must be
reviewed if a later legitimate charger or board source change updates them.


## Native #48 low-current RGB integration

The earlier correctness patches above remain separate from the functional
trial in `0004-g965n-low-current-led-trial.patch`. This trial uses the corrected
upstream LED driver with its original copyright/GPL notice. It attaches three
board software nodes to the existing unbound PMIC RGB platform child. No PMIC
parent reprobe, DT/BOOT update, charger change or direct userspace I2C access is
needed. Explicit driver_override selects only max77705-rgb; no automatic OF
match is added. Board compatible and parent I2C address0x66 are checked.

Lineage's pinned RGB source maps WHITE/RED/GREEN/BLUE to channels0/1/2/3.
The trial never registers white or changes its enable bits. Brightness codes
are restricted to0..1, below that reference driver's default low-power code5;
this is a register-code limit, not a calibrated optical/electrical-current claim.
Hardware blink/ramp remain unqualified; the callback returns EOPNOTSUPP so LED
core can use software timing. A read-only attribute reads only documented LED
registers0x30 and0x32..0x34, not IRQ/status registers or charger settings.

Build from the reviewed kernel source (patch0001 already applied), using the
qualified module-output tree with its exact Module.symvers:

```sh
python3 experiments/pmic/build-led-trial.py \
  --kernel-source "$KERNEL_SOURCE" --kernel-out "$KERNEL_OUT" \
  --output "$NEW_PRIVATE_MODULE_OUTPUT"
```

LED_TRIAL.json pins the input/output/patch and qualified ABI hashes. The build
creates a new directory and does not modify kernel source or flash a handset.
It copies the matching standard led-class-multicolor dependency. Changed ABI
or source requires a separate review, not bypassing hashes.

After explicit SM-G965N/BOOT/backup checks, stage the two modules, generated
pins.json and led-control.py in root-owned0700 `/usr/local/lib/g965n-led-trial`
with files0600. The control script checks the current sensor profile/BOOT and
RECOVERY/EFS/CPEFS/RADIO backup hashes before operations. Use:

```sh
sudo python3 /usr/local/lib/g965n-led-trial/led-control.py start \
  --confirm-sm-g965n-backed-up-led-trial
sudo python3 /usr/local/lib/g965n-led-trial/led-control.py test \
  --confirm-sm-g965n-backed-up-led-trial
sudo python3 /usr/local/lib/g965n-led-trial/led-control.py stop \
  --confirm-sm-g965n-backed-up-led-trial
```

The test refuses busy LEDs, checks each channel's current/enable readback and
uses finally to turn all three off. Stop unregisters only this child driver,
clears its override and unloads the trial module. It never removes/reprobes the
PMIC parent. The standard multicolor dependency may remain loaded.

For verified installations only, install g965n-led.service under
/etc/systemd/system, daemon-reload and enable it. Startup defaults to all LEDs
off. Standard paths are `/sys/class/leds/{red,green,blue}:indicator` with
max_brightness1. Normal user writes are not granted globally. No GNOME
notification/charging policy is installed by this trial.

Hardware evidence2026-11-20: fifteen on/off pulses passed exact register
readback; the owner saw blue/red/green light. Stop/start followed by another
test passed. Separate warm reboot auto-loaded the service and all three
readback tests passed again; failed units0. Brightness remained limited to1.
This qualifies low-current RGB output and boot persistence, not calibrated
brightness, hardware patterns or notification-daemon integration.

A broader PMIC regression first lacked the expected repository layout, then
correctly detected a stale full-DTS pin. Reviewed commit91d74ac's CPU-cache-only
DTS change and proved the charger node byte-identical to the original. Updated
only that topology reference pin; all three actual-C/fault-injection tests pass.

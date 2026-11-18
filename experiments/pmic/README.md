# MAX77705 source correctness candidates

These two patches are **source-only and hardware-unverified**. They do not add
DT nodes, change kernel configuration, enable a driver, write a PMIC register,
build a kernel, or install anything.

`SOURCES.json` pins the clean cached kernel commit, both input and output file
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
If applying fails, preserve the checkout for review. The tests copy the two
source files to a temporary tree; they do not change the supplied checkout.
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

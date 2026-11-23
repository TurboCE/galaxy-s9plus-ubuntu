# Read-only USB-C source diagnostic

This optional, root-only diagnostic was built and read on SM-G965N native #50.
It uses the existing `s9p-max77705-muic` I²C client. It reads BC, CC and PD
status registers; it never reads IRQ-clear registers, sends MCU opcodes,
changes roles, resets firmware, or writes ICs. It is not a charging policy.

Pinned register references and attribution: [USBC_REFERENCE.json](USBC_REFERENCE.json).
New code is GPL-2.0-only. The Samsung/Maxim reference files retain their original
notices upstream; no firmware or binaries are distributed here.

Build with the already-qualified kernel source/output and ARM64 cross compiler:

```sh
python3 experiments/charging/build-usbc-source.py \
  --kernel-source /path/to/mainline \
  --kernel-out /path/to/qualified-output \
  --output /path/to/new-isolated-module-output
```

The builder checks the qualified Module.symvers hash and writes a module hash
receipt. It never connects to a device, loads a module or flashes. The canonical
builder and `KCFLAGS=-Werror` build passed with the qualified native output.
Device deployment is separate: check actual model, kernel/ABI, protected backups,
module hash and authorization first; preserve ownership records for removal.
This optional module is not enabled at boot by this change.

After separately guarded loading with `enable_g965n=1`, root can read
`/sys/module/g965n_usbc_source/parameters/source`. Missing/wrong-owner clients or
failed reads return errors. Status fields are sequential reads, not an atomic
PD contract snapshot. A disappearing client fails rather than being rebound.

Observed BC type1 (SDP), sink state1, CCI3 and PD-ready do **not** prove an active
3A PD contract or a host's physical current ceiling. Do not use these fields alone
to raise input current, bypass thermal protection, or change firmware. A source
transition must be handled conservatively by any future charging policy.

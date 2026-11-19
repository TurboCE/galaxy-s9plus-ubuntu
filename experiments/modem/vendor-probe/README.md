# Owner RIL dependency probe

This original GPL-2.0-only source checks whether this G965N owner's Android
radio library can load under Bionic in the private runtime. It resolves the
`RIL_Init` symbol but **never calls it or any radio request**. It is a step
before comparing missing modem initialization, not an LTE service or a data
connectivity pass.

The tested profile is G965NKSU5FVA2 / native kernel43. Owner ELF files, linked
probe executables, raw logs and runtime receipts stay private and are not CI
artifacts. No redistribution rights to vendor software are assumed. No vendor
implementation or Android startup implementation is copied into this source.
The Linux UAPI headers are normal build inputs, not bundled vendor material.

## Known build path

Obtain `libc.so`, `libdl.so` and `linker64` from the owner's read-only runtime
APEX, preserving them locally under `.local/context/private-bionic-probe-inputs`.
The build helper verifies the exact reviewed hashes and AArch64 ELF ABI; it
refuses other firmware rather than guessing a startup ABI. The owner libc uses
the raw-stack program-launch ABI and a fini-array vector field at offset16,
verified for this profile. The original small bootstrap supplies an empty vector.
General Bionic program startup is described in the [AOSP source](https://android.googlesource.com/platform/bionic/+/master/libc/bionic/libc_init_dynamic.cpp);
this profile is also checked against the actual owner ELF.

Inside the existing Linux builder, generate userspace headers first:

```sh
make -s -C /build/src/mainline O=out ARCH=arm64 \
  INSTALL_HDR_PATH=/src/.local/context/vendor-probe-uapi headers_install
python3 /src/scripts/g965n/build-vendor-probe.py \
  --owner-bionic /src/.local/context/private-bionic-probe-inputs \
  --uapi /src/.local/context/vendor-probe-uapi \
  --output /src/.local/context/vendor-probe-build-1
```

Use a new output directory per build. The build-only helper never accesses or
flashes a device. Raw kernel headers fail userspace checks; do not suppress the
warnings. Sanitized `headers_install` output fixes that issue. The owner dynamic
interpreter supplies `ld-android.so` / shared-loader globals, so transitive
Bionic shared-library references are resolved at runtime; the probe's own
references still must resolve. PIE, RELRO and stack protection remain enabled.

For a Linux host policy check without any owner library load:

```sh
gcc -Wall -Wextra -Werror -DG965N_PROBE_HOST_TEST \
  experiments/modem/vendor-probe/probe.c -ldl -o /tmp/g965n-probe-host
/tmp/g965n-probe-host --self-test
```

## Guarded native path

Use `scripts/g965n/run-vendor-probe.py --help` for explicit model, current
startup/backup receipts and their hashes, verified guard/runtime helpers,
reviewed binary/hash, private lab and consent flags. Run `--phase self-test`
first, then `--phase inspect` with the same binary, lab and device boot.
The launcher refuses inspection without a matching successful native self-test.
It also requires the modem module absent and no private EFS/CPEFS/RADIO bindings.
The lab must be a new direct child of the checked private runtime data directory.
Nothing requires stopping the already functional audio/wireless services.

The process is limited to10seconds in a read-only, device-closed unit. Its
architecture-checked syscall filter permits read-only opens and stdio writes;
all device ioctls, sockets and filesystem mutations are denied. The self-test
checks those denials and the filesystem-metadata query needed by the loader.
File-system metadata reads remain permitted; no modem control was allowed to
fix the first `fstatfs` loader failure. Include both runtime APEX `lib64/bionic`
and parent `lib64` paths: the latter supplies the owner `libandroidicu.so`.
This correct search path is built into the launcher.

Native43 public launcher output after self-test and inspection:

```json
{"phase":"self-test","returncode":0,"verified":true,"records":[{"readonly_self_test":true,"ril_init_called":false}]}
{"phase":"inspect","returncode":0,"verified":true,"records":[{"library_loaded":true,"ril_entry_present":true,"ril_init_called":false}]}
```

Private logs preserve failures; sanitized output exposes only fixed boolean
records, not owner logs/identifiers. Inspection proves loader/dependency and
containment behavior only. RIL callback ABI, initialization, property handling,
private NV writes, persistent servicing, radio/data and shutdown are not
qualified by this result and need separate reviewed stages.

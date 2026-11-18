# Exact kernel #21 FUSE add-on (not loaded)

This is a temporary, opt-in compatibility add-on for the owner's already
running SM-G965N kernel #21. The native config was captured and matches the
reviewed build cache byte for byte: `CONFIG_FUSE_FS=m`, `CONFIG_CUSE=m`, and
MODVERSIONS disabled. A missing FUSE device was reported by the desktop document
portal on both private and stock Mesa. This source recipe is not hardware proof
of a working FUSE mount or portal.

The add-on builds only the unchanged upstream `fs/fuse/fuse.ko`. It does not
include CUSE, firmware, a systemd unit, an image, or an automatic loader. It never
flashes, replaces a filesystem profile, unloads a module, restarts the portal or
reboots. A later kernel may enable built-in FUSE; that is a separate kernel
change. Do not change the compatibility cache from `m` to `y`.

## Pinned inputs

The recipe requires Linux source commit
`8cd9520d35a6c38db6567e97dd93b1f11f185dc6`, clean `fs/fuse` and selected VFS headers,
unchanged tracked common/ARM64 headers, the exact native #21 config,
matching startup manifest and BOOT file, and the
same GCC 13.3.0 toolchain. It records every FUSE source and selected VFS header
SHA, generated ABI-header hashes, compiler, source/recipe commits, original
startup receipt, original backup-manifest hash, and these immutable link inputs:

| Input | SHA-256 |
| --- | --- |
| native decompressed `.config` | `71e2df2692ff368b642756cbd66a2b4117d9aeb102fe8dce2f76db107e461f0a` |
| `vmlinux` | `01b16afc87d0b41f3073f2c4f4e941e659ae4757b0e305b2d0d644a5a490c2bc` |
| `Module.symvers` and `vmlinux.symvers` | `11b780dda68ae6c544ceaa6fd4890bd2dc331743763ff2dcff456f02c5d839f0` |

UTS version is `#21 SMP PREEMPT Wed Nov 18 20:51:24 UTC 2026`; release is
`7.1.0-dirty`. Other object-only compilations may have changed build bookkeeping
without relinking `vmlinux`; neither a bookkeeping counter nor matching release
alone establishes compatibility. Exact hashes and the original startup receipt
are required.

The Linux FUSE implementation and its original source notices stay in the
upstream tree. Its Makefile is GPL-2.0-only, and source files retain their GNU GPL
notices and upstream authorship, including Miklos Szeredi. No upstream
source is copied into this directory. The new Python recipe, loader and tests
are GPL-2.0-only. Refer to upstream `fs/fuse/` and `COPYING` at the pinned commit
for the complete original source and license; preserve them when distributing a
built module. This repository does not publish the module, native config,
backup, extracted firmware, private receipts or diagnostic logs.

## Build after review and committing this recipe

Use only image `s9-g965n-builder:24.04.3` and volume
`s9-g965n-repro-build`. The old `s9-ubuntu-g965n-local` container has a different
kernel cache and must not be used. An example host invocation, after supplying
the exact private files under the ignored `.local/` directory, is:

```sh
fuse_git_common=$(git rev-parse --path-format=absolute --git-common-dir)
docker run --rm --network none \
  -v s9-g965n-repro-build:/build \
  -v "$PWD:/src:ro" \
  -v "$fuse_git_common:$fuse_git_common:ro" \
  -v "$PWD/.local/fuse-addon:/addon" \
  --entrypoint /usr/bin/python3 s9-g965n-builder:24.04.3 \
  /src/experiments/fuse/build-addon.py build \
  --source /build/src/mainline --kernel-out /build/src/mainline/out \
  --native-config /src/.local/context/kernel21-native.config \
  --startup-receipt /addon/inputs/startup21.json \
  --boot /addon/inputs/boot21.img \
  --backup-manifest /addon/inputs/verified-nine-partition-backup.json \
  --build-out /build/fuse-addon-native21-unique \
  --output /addon/package-unique --consent-host-build
```

The private input filenames above are placeholders, not preinstalled artifacts.
The read-only Git metadata mount lets a linked worktree verify its committed
recipe despite its absolute `.git` pointer; it grants no repository writes.
The source recipe must be committed and clean only under `experiments/fuse/`;
other agents' unrelated work does not block it. For read-only input verification
use action `inspect`, omit `--consent-host-build` and `--build-out`, and mount the
build volume read-only. `--output` remains required but is not created in inspect.

The recipe copies the existing complete output cache into a new build-output
snapshot, then invokes only:

```sh
make -C KERNEL_SOURCE O=NEW_SNAPSHOT ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- -j2 fs/fuse/fuse.ko
```

Ambient compiler/module override flags are removed for that command so the
pinned toolchain and native configuration determine the module build.

This avoids modifying the original #21 output/cache config or symbol table.
Afterward original pinned inputs must still match; snapshot config, linked
kernel and `vmlinux.symvers` must also remain unchanged. Snapshot
`Module.symvers` may only add FUSE exports while retaining every original entry.
The output receipt pins the module's SHA, ELF AArch64 type, GPL license, exact
vermagic, empty dependency list, and package helpers. Failures preserve the
output/snapshot and log for review; never retry by relaxing ABI checks.

## One explicit native load, after separate review

Transfer the package into a new root-owned directory under
`/var/lib/g965n-fuse-addon/`, mode 0700. All ancestors/helpers/receipts/module must
be ordinary root-owned paths, never writable by the user or a group and never
symlinks. Keep private backup metadata out of Git. Independently verify the
owner's complete nine-partition backup and provide its pinned manifest in the
package. The confirmation flag records the operator's completed backup check;
it does not rehash backup images itself.

Invoke the packaged loader with the package receipt SHA and explicitly selected
#21 BOOT SHA:

```sh
sudo python3 /var/lib/g965n-fuse-addon/UNIQUE/load-once.py \
  --package /var/lib/g965n-fuse-addon/UNIQUE \
  --expected-receipt-sha256 PACKAGE_RECEIPT_SHA256 \
  --expected-boot-sha256 CURRENT_BOOT21_SHA256 \
  --model SM-G965N --confirm-backup-verified --consent-load-once
```

Before one `insmod`, it verifies explicit consent/model/backup confirmation,
root-private package paths, original startup receipt and its hash, the packaged
existing `deploy-drivers.py` verifier, running kernel UTS/board/actual BOOT,
exact decompressed `/proc/config.gz`, module hash, AArch64 ELF, GPL metadata and
exact vermagic. It refuses if FUSE is already loaded. A root-private exclusive
lock prevents overlapping invocations, and the verified module FD stays open
through `insmod` so replacing its pathname cannot change the loaded bytes.
There are no force flags or automatic retries. A successful `insmod` does not
prove `/dev/fuse`, a mount or the document portal works; root must separately
verify those without resetting services implicitly.

## Host tests

```sh
python3 experiments/fuse/test_fuse_addon.py
```

Synthetic ELF tests reject wrong architecture/license/vermagic/dependencies and
invalid section bounds. Loader tests mock all device accesses and verify kernel
checks precede exactly one FD-pinned insmod; missing consent/backup, wrong
receipt, config or module cannot load anything. No test loads a native module.

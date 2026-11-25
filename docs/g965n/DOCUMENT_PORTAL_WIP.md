# Document portal / FUSE work in progress

This deferred work is isolated from the driver/system branch at the owner's
request. Do not merge or deploy it as part of the active hardware port work.

## Actual status

The native #21 kernel config has FUSE_FS=m, but its FUSE module is not shipped.
The document portal reports a missing FUSE device in both stock and private
Mesa sessions. This observation is independent of GPU rendering correctness.

The exact-kernel recipe passed six host tests on Mac/Linux and actual read-only
input checks. An isolated host build of fs/fuse/fuse.ko completed successfully;
original config, linked kernel and symbol inputs were preserved and the
resulting module/package passed the recipe's ELF, license and ABI metadata
checks. These are host build results, not a native mount or portal success.

**No FUSE module has been loaded or installed on the handset.** No portal
service was reset, no persistent loader was installed, and the main kernel
configuration was not changed. Further implementation and native validation
are paused. The private host artifact remains ignored under .local/fuse-addon/;
no binaries, native configuration, backup metadata, logs or firmware are in
this branch.

The implementation and its explicit checks are documented in
[experiments/fuse/README.md](../../experiments/fuse/README.md). Preserve upstream
source notices and the GPL-2.0-only terms of the new helper/test code.

## Earlier source checkpoints

The following checkpoints precede the final host build and explain the input
path correction; their pending-build wording is historical.

The user document portal also fails because /dev/fuse is unavailable. Both
private and restored stock sessions show it. Native#21 config has FUSE_FS=m
and exactly matches the cached21 configuration byte-for-byte; the module is
not supplied by the current image workflow. A source-only compatibility-addon
recipe is being prepared; no FUSE module has been loaded yet.

Prepared the exact#21 FUSE compatibility recipe with six host tests. Initial
read-only inspection stopped at a nonexistent legacy include/linux/fuse.h;
the pinned source uses include/uapi/linux/fuse.h and fs/fuse's own headers.
Corrected that input list while retaining a clean check across all tracked
common/ARM64 headers. Actual read-only inspection then verified native config,
compiler, source,21 vmlinux and both symbol tables. No module build/load yet.

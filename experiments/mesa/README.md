# Mesa 25.2.8 explicit modifier diagnostic patch

This patch makes Panfrost's explicit resource creation respect the existing
format/modifier capability callback. It is a diagnostic candidate, **not evidence
that the S9+ GPU timeout is repaired**. No device build, installation or hardware
trial is included in these results.

## Source and license

- Upstream: [Mesa 25.2.8 release notes](https://docs.mesa3d.org/relnotes/25.2.8.html)
- Archive: [mesa-25.2.8.tar.xz](https://archive.mesa3d.org/mesa-25.2.8.tar.xz)
- Official archive SHA-256, verified against the local archive:
  `097842f3e49d996868b38688db87b006f7d4541e93ce86d2f341d8b3e7be7c93`
- Sole target: `src/gallium/drivers/panfrost/pan_resource.c`
- Pristine target SHA-256:
  `445916b95a284b4f49d76491d60143754976bc7deacabbf4df3bfc56ad7f7eeb`
- Patched target SHA-256:
  `ba87b87903b99dc75848c4a297fb0cbee5008ef126a0357caa6677068808d605`
- Patch SHA-256:
  `cddfef5672d8fb927cb2ab15ea6753d931e04b49da504bfde94b10cc212b4bbc`

The full upstream copyright, author and MIT permission/disclaimer notice is
retained in [LICENSE.pan_resource.MIT](LICENSE.pan_resource.MIT). The original
source file's notice is unchanged. This Mesa-derived patch and standalone
regression helper use that MIT license; licenses of other project components
remain unchanged. No proprietary firmware, binary, disassembly, credentials,
private logs or device identifiers are included.

## Exact behavior

In `panfrost_resource_create_with_modifiers`, both native and emulated candidate
loops now require `screen->is_dmabuf_modifier_supported(...)` in addition to
membership in the caller's candidate list. Panfrost registers this callback as
`panfrost_is_dmabuf_modifier_supported` in `pan_screen.c`; its modifier walk uses
`dev->has_afbc` and format capabilities. Thus `PAN_MESA_DEBUG=noafbc` also affects
this explicit creation path.

The candidate preference order stays unchanged. A list containing AFBC and LINEAR
can select LINEAR when AFBC is disabled. An AFBC-only list then returns `NULL`;
it must not assert or silently allocate a layout the caller did not offer. An
unsupported emulated list likewise fails. The previous special case of **only**
`DRM_FORMAT_MOD_INVALID` continues to use the existing implicit creation fallback;
a mixed list containing INVALID does not gain a new fallback.

Imported resources, default/implicit layout selection, global flags and the
capability callback itself are untouched. This patch does not force LINEAR:
another supported explicit modifier can still be selected. In particular, a
compositor offering no compatible alternative may cause EGL allocation failure;
that is an unsupported combination, not a successful GPU rendering result.

## Host-only regression

With a pristine Mesa source tree available:

```sh
python3 experiments/mesa/test_modifier_filter.py --mesa-source /path/to/mesa-25.2.8
```

The helper verifies the exact upstream target hash, copies only that file into a
temporary ignored `.local/` directory, applies the patch with zero fuzz and
checks the expected patched hash. It verifies every byte outside the one edited
function is unchanged, including `panfrost_resource_from_handle`, defaults and
source notices. The cached/upstream tree is checked unchanged afterward.

It compiles the actual original and patched functions with minimal pipe types,
representative modifier tables and a faultable capability/allocation callback.
Thirteen C scenarios cover the original noafbc bypass, mixed/AFBC-only lists,
enabled-AFBC preference, native and emulated support rejection, unknown/empty
lists, unchanged only-INVALID fallback, no mixed-INVALID fallback, supported
alternatives and unchanged allocation failure behavior. These are selection
regressions, not Mesa-wide conformance or hardware modifier support tests.

To apply to a separate private source copy for a later reviewed build:

```sh
patch --batch --forward --fuzz=0 -p1 \
  -d /path/to/private/mesa-25.2.8 \
  -i /absolute/path/to/0001-panfrost-check-explicit-modifier-support.patch
```

Do not apply to the preserved source baseline. A future hardware comparison must
record the exact libraries used, successful rendered frames and actual presented
modifier. A presented LINEAR copy alone may not identify the rendering image on
a separate render/display GPU path. No GPU repair claim follows from applying or
building this patch.

## AArch64 four-channel byte swizzle

`0002-mesa-neon-ubyte4-swizzle.patch` speeds up the Mesa byte-to-byte
texture conversion observed in GNOME overview profiling. It selects the
NEON table lookup for four-channel unsigned-byte source and destination
arrays on AArch64 with NEON enabled. The helper supports zero and one
fill channels, unaligned buffers, in-place conversion and scalar tail
pixels. Other channel counts, types and unsupported selectors take the
existing conversion path.

The patch targets Mesa 25.2.8 `src/mesa/main/format_utils.c` and
preserves the source's [Intel MIT notice](LICENSE.format_utils.MIT).
Its SHA-256 is
`cd95fe92bc4e78dab8caaad98fb9741006cb994036963a16c75d68d7d147b65e`.
The source hashes before and after patching are pinned in the
regression below. The modifier patch targets a separate source file.

On an ARM64 machine with a C compiler and sanitizer runtime:

```sh
python3 experiments/mesa/test_ubyte4_swizzle.py --mesa-source /path/to/mesa-25.2.8
```

The native S9+ trial rebuilt the changed object, Mesa archive and
Gallium shared library in a separate build copy. Standard EGL/GLES
readback using the exact trial library passed 100 frames alternating
RGBA and BGRA uploads, with 6,553,600 output bytes compared. A GNOME
comparison on a virtual monitor showed no consistent animation
improvement and did not reproduce the physical screen's stutter.
The live GNOME session continues to use its accepted profile.
See [the GPU notes](../../docs/g965n/GPU.md) for the timing results.


## Qualified physical Shell overlay (native48)

Unlike the earlier virtual-monitor comparison, actual connected DSI A/B/A
reproduced and reduced opening paint p95 from22..25ms to11..14ms; restoration
returned22..25ms. Frame-clock dispatch still reaches17..24ms, so this is not a
complete animation repair. See [GPU evidence](../../docs/g965n/GPU.md).

`physical-session.py` stages only a new per-user Shell wrapper/vendor/drop-in,
verifies current SM-G965N BOOT and protected backups, and preserves the accepted
parent profile. `apply --help` lists the explicit model/backup/desktop-restart
confirmation and source/library pins. Stage the reviewed helper
`scripts/g965n/mesa-session-trial.py` as a root-private file; do not import a
user-writable helper as root. Apply first arms an independent240s restore timer.
Only `keep` with current private physical A/B, pixel and stable Shell mapping
evidence retains the overlay. This utility is separate from all build scripts.

The qualified on-device child is `physical-neon48-final`; `mesa43-full` remains
the parent fallback. To undo the child, run as root:

```sh
python3 /var/lib/g965n-mesa-trial/physical-neon48-final/session.py restore \
  --state /var/lib/g965n-mesa-trial/physical-neon48-final
```

Restore this child before changing its parent. Libraries are not overwritten.
The actual warm reboot retained coherent candidate EGL/Gallium/GBM mappings
and a Panfrost render descriptor; matching GPU faults and failed units were0.

### Clean source/build reproduction

Use native ARM64 Linux, Python3.12+, the previously documented private
Meson1.4.1/LLVM18 toolchain and pinned Mesa25.2.8 archive. As a normal user,
from this repository, choose a new private work directory:

```sh
python3 scripts/g965n/build-mesa-diagnostic.py prepare --variant neon \
  --work-dir /path/to/new-private-work --mesa-archive /path/to/mesa-25.2.8.tar.xz
python3 scripts/g965n/build-mesa-diagnostic.py build --variant neon \
  --work-dir /path/to/new-private-work --meson /path/to/private-venv/bin/meson
python3 scripts/g965n/build-mesa-diagnostic.py verify --variant neon \
  --work-dir /path/to/new-private-work
```

Both modifier and swizzle patches are SHA-pinned, applied with zero fuzz, and
resulting source file/tree hashes are verified. Neither build nor verify
installs libraries, restarts the desktop, writes partitions or flashes.
Old receipts pin the previous builder: preserve them and use a new directory.
The qualified running binary was incrementally rebuilt in an isolated copy;
clean source preparation/configure and the full1325-step rebuild passed.
The clean output separately passed100-frame/6,553,600-byte exact readback and
256MiB textures with actual Panfrost mappings. The running Shell retains its
previously qualified overlay; clean-build readback is not its adoption proof.

### Exact RGBA/BGRA readback

As the normal desktop user on the device:

```sh
cc -O2 -Wall -Wextra -Werror experiments/mesa/gpu-readback-bgra.c \
  -o /path/to/private-work/readback -lEGL -lGLESv2
python3 /path/to/completed-build/neon/launch.py -- /path/to/private-work/readback
python3 /path/to/completed-build/neon/launch.py -- \
  /path/to/private-work/readback --pressure-mib 256
```

Check reported renderer and mapped Gallium path against the expected build,
not just exit status. Qualified incremental candidate passed200 frames,
13,107,200 bytes and256MiB live textures with zero mismatches. This offscreen
test checks pixel correctness/pressure, not actual scanout FPS.

## Rejected tile32 candidate and residual opening analysis

Patch0003 targets the aligned32-bit, non-depth/stencil tiled-image path on
little-endian ARM64 NEON. Original notices are preserved in the source and
[LICENSE.pan_tiling.MIT](LICENSE.pan_tiling.MIT). `TILE32_TRIAL.json` pins the
exact source and patch. `test_tile32.py --mesa-source /path/to/mesa-25.2.8`
compares the actual scalar/candidate loops:2,688 store/load cases, offsets,
padding and guard bytes passed both ASan/UBSan and optimized ARM64 execution.

`build-tile32.py --baseline-build /path/to/qualified-build --output /new/copy`
rebuilds three final Ninja targets in a new complete ordinary-user build copy.
It does not install or restart a desktop. The baseline must be a locally
reviewed build, including its generated commands; it is not a sandbox for an
untrusted build tree. The clean builder's optional `--variant neon-tile32`
also pins/prepares all three patches, but its complete fresh build remains
unverified. Use the qualified `neon` variant for the accepted configuration.

Candidate GPU readback100frames/6,553,600bytes and256MiB passed. Synthetic
tiling improved, but the real DSI scene showed no consistent latency gain;
the child trial was explicitly rolled back and original NEON mappings verified.
Do not adopt this patch as an animation fix. `physical-session.py` can inventory
a hash-checked accepted parent overlay without executing its wrapper, and
requires the child override to sort after it. Four parsing/drift/escape tests
passed. Parent libraries and settings are preserved on child rollback.

`analyze-opening.py --events /private/events.json --marks /private/marks.tsv`
reports each of four openings per scene. Three tests cover incomplete captures
and pooled-percentile sample-count artifacts. Completion notifications are
compositor events, not scanout or photometric FPS. For the separately qualified
500ms CPU-frequency hint, see [interactive boost](../interactive-boost/README.md).
The owner accepted current performance; no further tuning/reboot was performed.

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

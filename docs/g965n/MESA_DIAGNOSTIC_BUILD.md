# Isolated Mesa diagnostic build

This build compares pristine Mesa 25.2.8 with the explicitly reviewed Panfrost
modifier-selection patch. It does not install libraries, update the system,
change a running graphics session, or execute GPU tests. A successful build is
not evidence that the G965N GPU works correctly.

The builder requires native Linux ARM64, a normal user, Python 3.12 or newer,
and a dedicated mode0700 work directory. Baseline and patched builds occupy
different subdirectories. Use one or two compilation jobs; this workflow does
not create swap or change memory limits.

## Prerequisites prepared separately

On Ubuntu 24.04, the reviewed preparation includes the normal C/C++ toolchain,
Ninja, pkg-config, patch, and these development packages:

```text
bison flex
python3-mako python3-packaging python3-yaml python3-ply python3-pycparser
python3-jinja2 python3-venv python3-setuptools
libdrm-dev libudev-dev libexpat1-dev libwayland-dev libwayland-egl-backend-dev wayland-protocols
libelf-dev libzstd-dev zlib1g-dev libglvnd-dev
llvm-18-dev libclang-18-dev libclang-cpp18-dev libclc-18-dev libclc-18
libllvmspirvlib-18-dev spirv-tools spirv-headers
```

The builder never installs these packages. Missing prerequisites stop the build.
Panfrost's compiler requires LLVM/CLC, a matching LLVM-SPIR-V translator, and
SPIRV-Tools 2024.1 or newer. Mesa's configure step checks their compatibility.
Use LLVM18 together with its matching development packages.
`libclc-18-dev` supplies metadata/headers; `libclc-18` also supplies the
`spirv-mesa3d-.spv` and `spirv64-mesa3d-.spv` files used by the compiler.

Ubuntu 24.04's Meson 1.3 is too old: this source requires Meson >=1.4.0. Use
**Meson 1.4.1 in a separately prepared private virtual environment with
`--system-site-packages`**, for example:

```sh
python3 -m venv --system-site-packages "$HOME/.local/share/g965n-mesa-tools"
"$HOME/.local/share/g965n-mesa-tools/bin/python" -m pip install --only-binary=:all: 'meson==1.4.1'
```

These are optional operator preparation commands, not actions performed by the
builder. Do not use root or global pip. The initial binary-only attempt at 1.4.2
had no matching wheel; 1.4.1 satisfies the source requirement. This does not
claim that the official 1.4.2 source distribution is absent.

## Pinned inputs

Place the release archive in the work directory's cache, using an existing
verified copy when available:

```text
/home/ubuntu/g965n-test/mesa-diagnostic/cache/mesa-25.2.8.tar.xz
```

The builder does not download it. Official release:
[Mesa archive](https://archive.mesa3d.org/mesa-25.2.8.tar.xz), with the checksum
published in [Mesa 25.2.8 release notes](https://docs.mesa3d.org/relnotes/25.2.8.html):

```text
097842f3e49d996868b38688db87b006f7d4541e93ce86d2f341d8b3e7be7c93
```

The patched variant applies only
`experiments/mesa/0001-panfrost-check-explicit-modifier-support.patch` using
`patch --fuzz=0`. Its pinned SHA256 is:

```text
cddfef5672d8fb927cb2ab15ea6753d931e04b49da504bfde94b10cc212b4bbc
```

The builder also checks the reviewed `pan_resource.c` hashes before and after
patching. Mesa's original license notices stay in the extracted source tree;
the diagnostic patch retains its MIT notice and attribution. This workflow
does not publish binaries or any device firmware.

## Prepare, configure, and build

Run from this repository checkout as the ordinary build user. Prepare the
private work directory before copying the cached archive:

```sh
mkdir -p "$HOME/g965n-test/mesa-diagnostic/cache"
chmod 700 "$HOME/g965n-test/mesa-diagnostic"
```

After copying the archive, build each variant independently:

```sh
python3 scripts/g965n/build-mesa-diagnostic.py self-test

python3 scripts/g965n/build-mesa-diagnostic.py prepare \
  --work-dir "$HOME/g965n-test/mesa-diagnostic" --variant baseline
python3 scripts/g965n/build-mesa-diagnostic.py configure \
  --work-dir "$HOME/g965n-test/mesa-diagnostic" --variant baseline \
  --meson "$HOME/.local/share/g965n-mesa-tools/bin/meson"
python3 scripts/g965n/build-mesa-diagnostic.py build \
  --work-dir "$HOME/g965n-test/mesa-diagnostic" --variant baseline \
  --meson "$HOME/.local/share/g965n-mesa-tools/bin/meson" --jobs 2

python3 scripts/g965n/build-mesa-diagnostic.py prepare \
  --work-dir "$HOME/g965n-test/mesa-diagnostic" --variant patched
python3 scripts/g965n/build-mesa-diagnostic.py configure \
  --work-dir "$HOME/g965n-test/mesa-diagnostic" --variant patched \
  --meson "$HOME/.local/share/g965n-mesa-tools/bin/meson"
python3 scripts/g965n/build-mesa-diagnostic.py build \
  --work-dir "$HOME/g965n-test/mesa-diagnostic" --variant patched \
  --meson "$HOME/.local/share/g965n-mesa-tools/bin/meson" --jobs 2
```

The selected configuration enables Wayland, Panfrost Gallium, private EGL/GBM,
GLVND, GLES2/3, desktop OpenGL and shared LLVM. Vulkan, GLX, Rusticl, video APIs,
tests and extra tools are disabled. Meson may not download subprojects.
The prefix points inside the private variant directory, but no install command
is run. Keep compilation logs and dependency preparation receipts privately.

During the first handset build, two CPU equivalents reached83C.
The operator reduced only the build service's CPU quota to one equivalent;
temperature fell to80C at the next observation. For long handset compilation,
use a bounded user service rather than assuming two jobs guarantee a low
temperature. For example, after configure, replace the direct build command:

```sh
systemd-run --user --unit=g965n-mesa-diagnostic-build \
  --property=CPUQuota=100% --property=MemoryMax=3G \
  --property=MemorySwapMax=0 --property=Nice=10 \
  --property=RuntimeMaxSec=10800 \
  /usr/bin/python3 "$PWD/scripts/g965n/build-mesa-diagnostic.py" build \
  --work-dir "$HOME/g965n-test/mesa-diagnostic" --variant patched \
  --meson "$HOME/.local/share/g965n-mesa-tools/bin/meson" --jobs 2
```

The first trial separately monitors temperatures and available memory and stops
only that build service at85C or sustained available memory below300MiB. Those
are experimental operator limits, not hardware specification limits, and the
builder itself does not implement a thermal monitor. CPU/GPU clocks and voltage
settings are unchanged by these service resource controls.

## Receipts and deliberate later execution

Each variant has `receipt.json`, a fresh source tree, `build/`, and eventually
`launch.py`. Receipts record the archive/patch/builder pins, complete source-tree
digest, configuration, host architecture, compiler/tool versions and executable
hashes, and the coherent runtime output hashes. Changed input, source or
recorded toolchain refuses reuse. Partial extraction/configuration is preserved;
choose a fresh work directory instead of deleting evidence or editing a receipt.
System development packages are prerequisites rather than a fully pinned OS
image, so this is not a promise of bit-identical builds across different hosts.

Verification does not run graphics:

```sh
python3 scripts/g965n/build-mesa-diagnostic.py verify \
  --work-dir "$HOME/g965n-test/mesa-diagnostic" --variant baseline
```

The builder emits `baseline/launch.py` and `patched/launch.py` only after their
builds complete. Neither launcher is executed automatically. An operator may
later invoke one with a separately authorized Wayland test command.

The launcher verifies its EGL vendor JSON, EGL library, Gallium library, GBM
library/backend and recorded library links. It selects
`build/src/egl/devenv_glvnd_egl.json`, whose vendor library path is absolute,
and sets private `LD_LIBRARY_PATH`, `GBM_BACKENDS_PATH` and
`LIBGL_DRIVERS_PATH` **only for its child process**. System GLVND dispatch may
remain the frontend; the Mesa vendor and Gallium/GBM components must come from
the same diagnostic build. Selecting only a private DRI driver with the system
Mesa vendor can fail `MESA_INTERFACE_VERSION_STRING` checks and is not this
comparison. No `ldconfig`, shell profile, global environment or compositor
configuration changes belong to this workflow.

Keep fd-based driver detection: the launcher clears an inherited
`MESA_LOADER_DRIVER_OVERRIDE` rather than forcing Panfrost on an Exynos display
fd. The Panfrost-only build automatically includes kmsro for the separate
display/render device path. Selecting private Mesa components does not require
overriding that device selection.

Record the variant receipt, explicit command, any child-only diagnostic flags,
actual chosen modifier, and device evidence for each later comparison. The
modifier patch does not establish that the native-resolution hang is fixed.

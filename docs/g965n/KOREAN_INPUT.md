# Korean touchscreen input

Ubuntu Noble GNOME46 passes a virtual keysym with hardware keycode zero from
its on-screen keyboard. Ubuntu ibus-hangul1.5.5-2build2 normalizes even that code
through a US hardware map. The phone comparison commits 가나다 from physical
codes but rejects all zero-code events. This is separate from font coverage.

The patch in `patches/ibus-hangul/` skips normalization only for zero. It retains
normalization for real keyboards. Native sources are US and IBus Hangul; an XKB
Korean layout alone is not a composing input method. Per-user source overrides
are preserved; the image supplies defaults for fresh users.

`bash scripts/g965n/build-ibus-hangul.sh /absolute/build-directory` downloads
SHA256-pinned Ubuntu upstream and packaging archives, applies the patch and
builds a local Debian package (no install/flash). Build dependencies are listed
in the image integration and Ubuntu source descriptor. The image builder uses
the same recipe inside its rootfs, installs the resulting ARM64 package and
marks newly added build dependencies for normal cleanup. A full image rebuild
has not yet been qualified with this addition.

Upstream: https://github.com/libhangul/ibus-hangul (tag 1.5.5).
Ubuntu source: https://ports.ubuntu.com/ubuntu-ports/pool/main/i/ibus-hangul/ .
Original source copyright/GPL notices and Debian copyright are retained in the
source/package. This repository publishes the change and recipe, not an engine
binary. Any distribution of a built engine must also supply its corresponding
source archives, this patch, packaging and build recipe under their existing
terms. Do not treat the project's firmware redistribution policy as permission
to publish vendor firmware.

Validation must cover both physical/virtual input, owner touchscreen composition
and a fresh login. Installing/selecting IBus alone was insufficient and must not
be recorded as an input fix. The local version is 1.5.5-2build2+g965n1; a future
Ubuntu package can supersede it, so recheck virtual input when changing versions.

#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Build only. No device access, installation or flashing.
set -euo pipefail
work=${1:?Usage: build-ibus-hangul.sh ABSOLUTE_BUILD_DIRECTORY}
[[ "$work" = /* ]] || { echo 'Build directory must be absolute' >&2; exit 1; }
repo=$(cd "$(dirname "$0")/../.." && pwd)
mkdir -p "$work"
cd "$work"
base=https://ports.ubuntu.com/ubuntu-ports/pool/main/i/ibus-hangul
fetch() {
    local name=$1 digest=$2
    if [[ ! -f "$name" ]]; then
        curl --fail --location --retry 3 "$base/$name" -o "$name.part"
        mv "$name.part" "$name"
    fi
    printf '%s  %s\n' "$digest" "$name" | sha256sum --check -
}
fetch ibus-hangul_1.5.5.orig.tar.gz f2f4967f90701c040a85657ea2ab9a1021d7d31f0061cf21b9dd90e026e49d2a
fetch ibus-hangul_1.5.5-2build2.debian.tar.xz 758596a4e5ec68393d70d60f7bc9ef299264f31c44b580bd5b447584f0af3f24
# Always unpack a clean source tree; retain source archives for corresponding source.
rm -rf ibus-hangul-1.5.5
tar -xzf ibus-hangul_1.5.5.orig.tar.gz
tar -xJf ibus-hangul_1.5.5-2build2.debian.tar.xz -C ibus-hangul-1.5.5
cd ibus-hangul-1.5.5
patch --batch --fuzz=0 -p1 < "$repo/patches/ibus-hangul/0001-honor-virtual-keyvals.patch"
python3 - <<'PY'
from pathlib import Path
p = Path('debian/changelog')
p.write_text('''ibus-hangul (1.5.5-2build2+g965n1) noble; urgency=medium

  * Preserve the supplied keysym for virtual keys without a hardware keycode.

 -- G965N port maintainers <noreply@localhost>  Thu, 19 Nov 2026 00:00:00 +0000

''' + p.read_text())
PY
dpkg-checkbuilddeps
dpkg-buildpackage -b -us -uc -j2

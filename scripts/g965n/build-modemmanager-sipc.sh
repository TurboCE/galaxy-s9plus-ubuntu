#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
if (( $# < 2 || $# > 3 )); then
    printf 'Usage: %s modemmanager_1.23.4.orig.tar.gz new-output-directory [meson-cross-file]\n' "$0" >&2
    exit 2
fi
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
archive="$(realpath -- "$1")"
output="$2"
cross=()
if (( $# == 3 )); then
    cross=(--cross-file "$(realpath -- "$3")")
fi

expected=4d413df4657142802b077db8cf2fee386bd6a144073ffe612d60672a244a7597
printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --status || {
    printf 'Expected the verified Ubuntu Noble ModemManager 1.23.4 source archive\n' >&2
    exit 1
}

# Require a fresh directory so an existing source tree or bundle cannot be replaced.
mkdir -- "$output"
output="$(realpath -- "$output")"
source="$output/source"
build="$output/build"
bundle="$output/bundle"
desktop="$repo/experiments/modem/desktop-sipc"
mkdir -p -- "$source" "$bundle/lib" "$bundle/plugins"
tar -xzf "$archive" -C "$source" --strip-components=1
patch --batch --forward -d "$source" -p1 < "$desktop/modemmanager-1.23.4-native-sipc.patch"
cp -R -- "$desktop/samsung-sipc" "$source/src/plugins/"

meson setup "$build" "$source" "${cross[@]}" --wrap-mode=nodownload \
    -Dauto_features=disabled -Dqmi=false -Dmbim=false -Dqrtr=false \
    -Dplugin_generic=enabled -Dplugin_samsung_sipc=enabled \
    -Dtests=false -Dintrospection=false -Dman=false -Dexamples=false \
    -Dbash_completion=false -Ddbus_policy_dir=/usr/share/dbus-1/system.d \
    -Dsystemdsystemunitdir=/usr/lib/systemd/system -Dudevdir=/usr/lib/udev
ninja -C "$build" -j "${G965N_MM_BUILD_JOBS:-4}" src/ModemManager \
    src/plugins/libmm-plugin-generic.so src/plugins/libmm-plugin-samsung-sipc.so

install -m 0755 -- "$build/src/ModemManager" "$bundle/ModemManager"
install -m 0644 -- "$build/libmm-glib/libmm-glib.so.0.10.0" "$bundle/lib/libmm-glib.so.0"
install -m 0644 -- "$build/src/plugins/libmm-plugin-generic.so" \
    "$build/src/plugins/libmm-plugin-samsung-sipc.so" "$bundle/plugins/"
printf 'Built isolated SIPC test bundle at %s\n' "$bundle"

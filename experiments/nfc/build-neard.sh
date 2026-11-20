#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Build only. Install and device deployment are separate operator steps.
set -eu
: "${1:?Pass a new build directory}"
revision=f4b6db9ec482208079f684a0ed6762fd37371d2b
test ! -e "$1"
git clone https://github.com/linux-nfc/neard.git "$1"
git -C "$1" checkout --detach "$revision"
test "$(git -C "$1" rev-parse HEAD)" = "$revision"
meson setup "$1/build" "$1" --prefix=/usr/local \
  -Dsystemd=enabled -Dp2p=false -Dese=false -Dtools=true -Dtest=true
meson compile -C "$1/build" -j2
meson test -C "$1/build" --print-errorlogs

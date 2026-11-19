#!/bin/bash
# Build the Ubuntu 24.04 root filesystem for the Galaxy S9+ from scratch.
#
#   sudo image/build-image.sh
#
# Output in dist/image/: s9plus-rootfs.img (a raw ext4 image for USERDATA)
# and SHA256SUMS. The kernel is a separate boot image (docs/02-building.md);
# it has every driver built in, so the root filesystem carries no modules.
#
# Settings (user, password, time zone, keyboard, SSH key) are described in
# image/common/lib.sh. Optional features are not installed: see extras/.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
. "$REPO/image/common/lib.sh"
WORK=${WORK:-/var/tmp/s9plus-image}
OUT=${OUT:-$REPO/dist/image}

require_host
image_settings s9plus
R=$WORK/rootfs
trap chroot_umount EXIT

rootfs_bootstrap "$R"
chroot_mount "$R"
rootfs_install "$R" "$REPO/device/packages.txt"
rootfs_configure "$R"
rootfs_device "$R" "$REPO/device/base" "$REPO/device/configure.sh"
# GNOME's touch keyboard supplies virtual keycode zero. Noble's original
# Hangul engine rejects it; build the pinned corresponding-source correction.
mkdir -p "$R/tmp/g965n-ime/scripts/g965n" "$R/tmp/g965n-ime/patches/ibus-hangul"
cp "$REPO/scripts/g965n/build-ibus-hangul.sh" "$R/tmp/g965n-ime/scripts/g965n/"
cp "$REPO/patches/ibus-hangul/0001-honor-virtual-keyvals.patch" "$R/tmp/g965n-ime/patches/ibus-hangul/"
in_chroot "$R" /bin/bash -eu -c '
    dpkg-query -W -f="\${binary:Package}\n" | sort > /tmp/ime-packages-before
    apt-get install -y --no-install-recommends appstream debhelper dh-apparmor \
        dh-python gettext libgtk-3-dev libhangul-dev libibus-1.0-dev \
        pkg-config python3 build-essential dpkg-dev
    bash /tmp/g965n-ime/scripts/g965n/build-ibus-hangul.sh /tmp/g965n-ime-build
    apt-get install -y /tmp/g965n-ime-build/ibus-hangul_1.5.5-2build2+g965n1_arm64.deb
    dpkg-query -W -f="\${binary:Package}\n" | sort > /tmp/ime-packages-after
    comm -13 /tmp/ime-packages-before /tmp/ime-packages-after | xargs -r apt-mark auto
    apt-mark manual ibus-hangul
    rm -rf /tmp/g965n-ime /tmp/g965n-ime-build /tmp/ime-packages-before /tmp/ime-packages-after
'
rootfs_finish "$R"
chroot_umount

mkdir -p "$OUT"
rm -f "$OUT/s9plus-rootfs.img" "$OUT/SHA256SUMS"
make_ext4 "$R" "$OUT/s9plus-rootfs.img" s9plus-root
checksums "$OUT"
log "done: flash $OUT/s9plus-rootfs.img to USERDATA (docs/03-installing.md)"

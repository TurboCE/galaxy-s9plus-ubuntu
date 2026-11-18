#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
set -a
. /run/image.env
set +a
test -n "${IMAGE_PASSWORD:-}"
test "$IMAGE_PASSWORD" != CHANGE_ME_BEFORE_BUILD
export WORK=/build/g965n-image OUT=/src/dist/image-g965n
export UBUNTU_MIRROR=https://ports.ubuntu.com/ubuntu-ports
mkdir -p /proc/sys/fs/binfmt_misc
if ! test -e /proc/sys/fs/binfmt_misc/register; then
  mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc
fi
if ! test -e /proc/sys/fs/binfmt_misc/qemu-aarch64; then
  grep '^:' /usr/lib/binfmt.d/qemu-aarch64.conf > /proc/sys/fs/binfmt_misc/register
fi
cd /src
# No device is accessible to this container. Never run any flash script here.
bash image/build-image.sh

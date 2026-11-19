#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
set -euo pipefail
cd /src
# A managed worktree's .git file may point outside the container. The host
# wrapper supplies its revision; direct callers must do the same if needed.
project_commit=${S9_PROJECT_COMMIT:-}
if [[ -z "$project_commit" ]]; then
  project_commit=$(git rev-parse HEAD) || { echo 'Set S9_PROJECT_COMMIT from the host checkout.'; exit 1; }
fi
[[ "$project_commit" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid source commit receipt.'; exit 1; }
export S9_PROJECT_COMMIT="$project_commit"
export BUILD=/build BUILD_IMG= UBUNTU_MIRROR=https://ports.ubuntu.com/ubuntu-ports
for f in bcmdhd_sta.bin_b2 nvram.txt_r02a_b2 bcmdhd_clm.blob regulatory.db regulatory.db.p7s; do
  test -s "firmware/$f" || { echo "Missing local firmware/$f. See firmware/README.md."; exit 1; }
done
mkdir -p /build/src /build/out /build/reference
if [[ ! -d /build/src/mainline/.git ]]; then
  git clone --depth 1 --branch v7.1 \
    https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git /build/src/mainline
fi
test "$(git -C /build/src/mainline rev-parse HEAD)" = 8cd9520d35a6c38db6567e97dd93b1f11f185dc6
test "$(git -C /build/src/mainline rev-parse v7.1)" = b3f94b2b3f3e51ab880a51fc6510e1dafba654ed
if [[ ! -x /build/out/busybox-arm64 ]]; then
  python3 scripts/build/fetch_busybox.py /build/out/busybox-arm64
fi
if [[ ! -f /build/reference/twrp.img ]]; then
  curl -fL --retry 3 -e https://dl.twrp.me/star2lte/twrp-3.3.1-0-star2lte.img.html \
    https://dl.twrp.me/star2lte/twrp-3.3.1-0-star2lte.img -o /build/reference/twrp.img
fi
echo '5b5d2290940203316024a94581107ffad17670bb2f596fd27ef483d3d2685994  /build/reference/twrp.img' | sha256sum -c -
find firmware device/base/lib/firmware -type f ! -name '*.md' -exec sha256sum {} + > /build/firmware-inputs.sha256
bash scripts/build/build_stable.sh
python3 scripts/g965n/verify-cache-dtb.py /build/src/mainline/out/arch/arm64/boot/dts/exynos/exynos9810-star2lte.dtb
if [[ "${S9_EXPERIMENTAL_AUDIO:-0}${S9_EXPERIMENTAL_BLUETOOTH:-0}${S9_EXPERIMENTAL_SENSORS:-0}${S9_EXPERIMENTAL_MODEM:-0}${S9_EXPERIMENTAL_IIO_BRIDGE:-0}" != 00000 ]]; then
  make -C /build/src/mainline O=out ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- modules_prepare
  # Image-only builds produce vmlinux.symvers, not the external-module table.
  # This image has no other module dependencies; use its own exact export list.
  cp /build/src/mainline/out/vmlinux.symvers /build/src/mainline/out/Module.symvers
  for feature in audio bluetooth sensors modem iio-bridge; do
    option="S9_EXPERIMENTAL_${feature^^}"
    option=${option//-/_}
    [[ "${!option:-0}" = 1 ]] || continue
    make -C /build/src/mainline O=out ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
      "M=/src/experiments/$feature" clean
    make -C /build/src/mainline O=out ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
      "M=/src/experiments/$feature" modules
    mkdir -p "dist/experimental/$feature"
    cp experiments/"$feature"/*.ko "dist/experimental/$feature/"
    if [[ "$feature" = modem ]]; then
      # Build the tracked GPL hardware overlay; never copy it onto a device.
      dtc -@ -I dts -O dtb -o dist/experimental/modem/modem.dtbo \
        experiments/modem/g965n-modem-overlay.dts
    fi
  done
fi
out=$(find dist -maxdepth 1 -type d -name 'm71-*' | sort | tail -1)
test -n "$out"
name="boot-g965n-experimental-$(date -u +%Y%m%dT%H%M%SZ).img"
TWRP_IMG=/build/reference/twrp.img bash scripts/build/pack_uniloader.sh "$out" "$name"
mkdir -p dist/g965n
cp /build/firmware-inputs.sha256 dist/g965n/
dpkg-query -W > dist/g965n/build-host-packages.txt
printf '%s\n' "$S9_PROJECT_COMMIT" > dist/g965n/project-commit.txt
git -C /build/src/mainline rev-parse HEAD > dist/g965n/kernel-commit.txt
sha256sum /build/out/busybox-arm64 > dist/g965n/busybox.sha256
sha256sum "dist/uniloader/$name" > dist/g965n/boot.sha256
features=()
for feature in audio bluetooth sensors modem iio-bridge; do
  option="S9_EXPERIMENTAL_${feature^^}"
    option=${option//-/_}
  [[ "${!option:-0}" != 1 ]] || features+=("$feature")
done
if (( ${#features[@]} )); then
  qualification=()
  # Only the explicit read-only owner input from build.sh qualifies comparison.
  # Never adopt an old cached stock image from the build volume.
  if [[ "${S9_EXPERIMENTAL_MODEM:-0}" = 1 && -f /run/g965n-stock-boot.img ]]; then
    qualification+=(--stock-boot /run/g965n-stock-boot.img)
  fi
  python3 scripts/g965n/package-experiments.py --kernel-out /build/src/mainline/out \
    --boot "dist/uniloader/$name" --output dist/experimental \
    --source-commit "$(cat dist/g965n/project-commit.txt)" --features "${features[@]}" \
    "${qualification[@]}"
fi
echo "BUILD_ONLY_COMPLETE: dist/uniloader/$name; SM-G965N hardware boot still requires qualification."

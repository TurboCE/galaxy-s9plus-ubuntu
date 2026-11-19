#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Build-only. No ADB, USB device access, or flash commands.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
ACTION=${1:-help}
IMAGE=${S9_BUILD_IMAGE:-s9-g965n-builder:24.04.3}
VOLUME=${S9_BUILD_VOLUME:-s9-g965n-repro-build}
STATE="$ROOT/.local"
case "$ACTION" in prepare|kernel|rootfs|all) ;; *)
  echo 'Usage: build.sh prepare|kernel|rootfs|all'
  echo 'Run prepare once; import your own firmware; then all. See README.md.'
  exit 0;; esac
mkdir -p "$STATE/context" "$STATE/logs"
if [[ "$ACTION" = prepare ]]; then
  python3 - "$STATE/context" <<'PY'
import hashlib, pathlib, sys, urllib.request
p = pathlib.Path(sys.argv[1]) / 'ubuntu-base-24.04.3-base-amd64.tar.gz'
expected = '6bc2cde3930ad088b3bb46fa45279e96d25bc3810f209850ecbe4722711874f9'
if not p.exists():
    u = 'https://cdimage.ubuntu.com/ubuntu-base/releases/24.04.3/release/' + p.name
    with urllib.request.urlopen(u, timeout=180) as response:
        p.write_bytes(response.read())
if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
    raise SystemExit('Ubuntu Base checksum mismatch; remove the cached archive and retry.')
PY
  cp scripts/g965n/Dockerfile "$STATE/context/Dockerfile"
  docker build --platform linux/amd64 -t "$IMAGE" "$STATE/context"
  docker run --rm --platform linux/amd64 -v "$ROOT/firmware:/output" "$IMAGE" \
    bash -c 'cp -L /lib/firmware/regulatory.db /lib/firmware/regulatory.db.p7s /output/'
  exit
fi
docker image inspect "$IMAGE" >/dev/null
docker volume create "$VOLUME" >/dev/null
RUN=(docker run --rm --platform linux/amd64 --cpus "${S9_BUILD_CPUS:-3}"
  --memory "${S9_BUILD_MEMORY:-4g}" -v "$VOLUME:/build" -v "$ROOT:/src"
  -e "S9_PROJECT_COMMIT=$(git rev-parse HEAD)")
for feature in AUDIO BLUETOOTH SENSORS MODEM IIO_BRIDGE PANEL_AOR; do
  option="S9_EXPERIMENTAL_$feature"
  if [[ "${!option:-0}" = 1 ]]; then RUN+=(-e "$option=1"); fi
done
if [[ -n "${S9_MODEM_STOCK_BOOT:-}" ]]; then
  [[ "${S9_EXPERIMENTAL_MODEM:-0}" = 1 && ( "$ACTION" = kernel || "$ACTION" = all ) ]] || {
    echo 'S9_MODEM_STOCK_BOOT requires an explicit experimental modem kernel build.'; exit 1; }
  stock_boot=$(python3 - "$S9_MODEM_STOCK_BOOT" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1]).expanduser()
if p.is_symlink() or not p.is_file():
    raise SystemExit('Stock BOOT must be a regular file, not a symlink.')
if not 8 <= p.stat().st_size <= 57671680:
    raise SystemExit('Invalid stock BOOT size.')
with p.open('rb') as stream:
    if stream.read(8) != b'ANDROID!':
        raise SystemExit('Invalid stock BOOT header.')
p = p.resolve()
if ':' in str(p):
    raise SystemExit('Stock BOOT bind path cannot contain a colon.')
print(p)
PY
  )
  RUN+=(-v "$stock_boot:/run/g965n-stock-boot.img:ro")
fi
if [[ "$ACTION" = kernel || "$ACTION" = all ]]; then
  "${RUN[@]}" "$IMAGE" bash scripts/g965n/container-kernel.sh \
    2>&1 | tee "$STATE/logs/kernel.log"
fi
if [[ "$ACTION" = rootfs || "$ACTION" = all ]]; then
  test -s device/base/lib/firmware/brcm/brcmfmac4361-pcie.bin || {
    echo 'Import your own firmware first; refusing an image without Wi-Fi firmware.'; exit 1; }
  test -s "$STATE/image.env" || {
    echo 'Create .local/image.env from scripts/g965n/image.env.example first.'; exit 1; }
  chmod 600 "$STATE/image.env"
  # SYS_ADMIN is for chroot mounts and arm64 binfmt inside the Linux Docker VM.
  # No --privileged, host root filesystem, Docker socket, or USB devices.
  "${RUN[@]}" --cap-add SYS_ADMIN --security-opt seccomp=unconfined \
    --security-opt apparmor=unconfined \
    -v "$STATE/image.env:/run/image.env:ro" "$IMAGE" \
    bash scripts/g965n/container-rootfs.sh 2>&1 | tee "$STATE/logs/rootfs.log"
fi

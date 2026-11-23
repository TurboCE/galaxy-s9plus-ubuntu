#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Build only: no installation, module loading, flashing or device access.
set -eu
: "${KERNEL_SOURCE:?Set reviewed kernel source directory}"
: "${KERNEL_OUT:?Set qualified configured kernel output directory}"
: "${DIAGNOSTIC_OUT:?Set a new absolute output directory}"
case "$DIAGNOSTIC_OUT" in /*) ;; *) echo 'Output must be absolute' >&2; exit 1;; esac
python3 - "$KERNEL_OUT/Module.symvers" <<'PY'
import hashlib,sys
from pathlib import Path
expected='45d68e3278f2498bb2d187c86b86c2803417d2c4dbcccbe096caf268dd6422e2'
if hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()!=expected:
    raise SystemExit('Unqualified kernel export ABI; do not bypass modpost')
PY
mkdir "$DIAGNOSTIC_OUT"
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for name in g965n-adc-v3 g965n-adc-board g965n-charge-snapshot; do
    cp "$source_dir/$name.c" "$DIAGNOSTIC_OUT/"
done
printf 'obj-m += g965n-adc-v3.o g965n-adc-board.o g965n-charge-snapshot.o\n' > "$DIAGNOSTIC_OUT/Makefile"
make -C "$KERNEL_SOURCE" O="$KERNEL_OUT" M="$DIAGNOSTIC_OUT" \
    ARCH=arm64 CROSS_COMPILE="${CROSS_COMPILE:-aarch64-linux-gnu-}" modules

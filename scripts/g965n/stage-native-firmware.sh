#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# Run on the native Ubuntu handset. Import only its own stock firmware.
# VENDOR is mounted read-only without journal replay. No partitions are written.
set -euo pipefail
[[ $EUID = 0 ]] || { echo 'Run as root on the handset.'; exit 1; }
tr '\0' '\n' < /sys/firmware/devicetree/base/compatible | grep -qx samsung,star2lte
[[ $(lsblk -n -o PARTLABEL /dev/sda19) = VENDOR ]]
mountpoint=$(mktemp -d /run/g965n-firmware.XXXXXX)
mounted=0
cleanup() {
  if [[ $mounted = 1 ]]; then umount "$mountpoint" || return; fi
  rmdir "$mountpoint"
}
trap cleanup EXIT
mount -t ext4 -o ro,noload /dev/sda19 "$mountpoint"
mounted=1
install -d /lib/firmware/brcm
for name in calliope_sram.bin calliope_dram.bin calliope_iva.bin; do
  test -s "$mountpoint/firmware/$name"
  install -m 644 "$mountpoint/firmware/$name" "/lib/firmware/$name"
  cmp "$mountpoint/firmware/$name" "/lib/firmware/$name"
done
# The module vendor must be chosen explicitly; do not infer it from other phones.
case "${1:-}" in
  semco|murata)
    source="$mountpoint/firmware/bcm4361B2_$1.hcd"
    test -s "$source"
    for name in BCM.samsung,star2lte.hcd BCM4361B2.hcd; do
      install -m 644 "$source" "/lib/firmware/brcm/$name"
      cmp "$source" "/lib/firmware/brcm/$name"
    done;;
  '') echo 'Audio firmware staged; Bluetooth vendor not selected.';;
  *) echo 'Expected semco or murata; Bluetooth firmware not staged.'; exit 1;;
esac
echo 'Own-device firmware staged locally. No hardware driver loaded.'

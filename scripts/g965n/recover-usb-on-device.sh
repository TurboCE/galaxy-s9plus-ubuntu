#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Run on the phone over Wi-Fi SSH or its USB serial console, with sudo.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Run this on the phone with sudo.' >&2; exit 1; }
tr '\000' '\n' < /proc/device-tree/compatible | grep -Fxq 'samsung,star2lte' || {
  echo 'Unexpected device; no network changes made.' >&2; exit 1;
}
nmcli --wait 15 connection up usb0-host
# A host that fell back to link-local may not immediately renew its DHCP lease.
# Re-enumerate the USB gadget while preserving the Wi-Fi recovery session.
systemctl restart usb-gadget.service
echo 'USB reconnected; allow the host to receive a fresh DHCP address.'

#!/bin/bash
# Galaxy S9+: hardware configuration, run inside the image during the build
# (image/build-image.sh). Only what this phone needs to work; the optional
# features are in extras/.
set -euo pipefail

chmod 600 /etc/NetworkManager/system-connections/usb0.nmconnection

# USB serial console and network, touch/charger power fix, the stability
# defaults, Wi-Fi reconnect after a failed rekey. hciattach-bcm4361.service
# stays off: the kernel is built without Bluetooth (build71.sh turns BT and
# RFKILL off), so it could only fail and restart every 3 s.
systemctl enable usb-gadget.service s9p-touch-power.service s9p-stability.service \
	s9p-wifi-guard.service serial-getty@ttyGS0.service s9p-usb-dhcp.service
dnsmasq --test --conf-file=/etc/dnsmasq.d/s9p-usb-only.conf

# The active desktop user's GPIO-only handler changes display power, not system
# sleep. Its dconf default leaves short power presses for that handler; existing
# user overrides and the screen lock/long-press policies are not rewritten here.
systemctl --global enable g965n-screen-button.service

# The common image sets up zram swap, but this kernel has no zram (and the
# image carries no modules): zram-generator would create dev-zram0.swap for
# a device that never appears, and every boot would wait 90 s for it, then
# report failed units. An empty generator config switches it off; 6 GB of
# RAM run the desktop without swap. The common zram tuning goes too: on a
# swap file on flash it would push memory out to UFS early.
ln -sf /dev/null /etc/systemd/zram-generator.conf
rm -f /etc/sysctl.d/90-zram.conf

# Suspend never resumes on this port (the M3 cores do not come back).
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target \
	suspend-then-hibernate.target

# Mesa's AFBC repacking corrupts textures on this Mali-G72 (16-pixel dashes
# in icons and text). /etc/environment is what reaches gnome-shell.
grep -q '^PAN_MAX_AFBC_PACKING_RATIO=' /etc/environment ||
	echo 'PAN_MAX_AFBC_PACKING_RATIO=0' >> /etc/environment

# G965N / Mali-G72: CRC transaction elimination reproduced fragment job hangs
# in Mesa25.2.8. nocrc passed the complete33-scene hardware suite with normal
# DVFS/runtime PM. Keep hardware acceleration; avoid this unqualified fast path.
# Preserve an existing explicit user debug policy rather than overwriting it.
grep -q '^PAN_MESA_DEBUG=' /etc/environment ||
	echo 'PAN_MESA_DEBUG=nocrc' >> /etc/environment

cat > /etc/fstab <<'FSTAB'
# The initramfs mounts USERDATA (/dev/sda25) as the root filesystem.
LABEL=s9plus-root  /  ext4  defaults,noatime  0 0
FSTAB

# The built-in panel at 3x leaves only 480 logical pixels. Firefox and many
# desktop dialogs have a larger minimum width. A fresh user's 2x profile gives
# 720x1480; existing user choices must not be overwritten by this build step.
phone_home=$(getent passwd "$IMAGE_USER" | cut -d: -f6)
phone_group=$(id -gn "$IMAGE_USER")
install -d -m 700 -o "$IMAGE_USER" -g "$phone_group" "$phone_home/.config"
if [[ ! -e "$phone_home/.config/monitors.xml" ]]; then
	install -m 644 -o "$IMAGE_USER" -g "$phone_group" \
		/usr/share/g965n/monitors-2x.xml "$phone_home/.config/monitors.xml"
fi
dconf update

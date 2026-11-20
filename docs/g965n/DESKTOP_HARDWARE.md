# Native desktop hardware controls

These notes describe the tested SM-G965N #48 handset, not feature parity
with Android. Installing an application does not create a hardware driver.

## Mobile Network

Ubuntu 24.04 GNOME Settings includes its `wwan` panel. With the guarded
desktop SIPC service running and ModemManager enumerating the modem, the
panel exposes mobile data, roaming, network mode, network selection, APNs,
SIM lock status and modem details. A visible control is not evidence that
every operation is implemented by this experimental backend. Do not use
SIM PIN changes or manual operator selection as a casual enumeration test.

GNOME's panel visibility depends on a modem with supported capabilities.
When the desktop LTE service cleans up, the stock manager has no modem
and the panel can disappear. This is different from a missing GNOME package.
The exact cause of an earlier missing-menu observation was not captured.

After the documented model, BOOT and backup checks, install the tracked
launcher separately on the handset:

```sh
sudo install -m 0644 experiments/modem/desktop-sipc/g965n-mobile-network.desktop \
  /usr/local/share/applications/g965n-mobile-network.desktop
desktop-file-validate /usr/local/share/applications/g965n-mobile-network.desktop
gio launch /usr/local/share/applications/g965n-mobile-network.desktop
```

This opens the standard Settings panel, not a custom APN editor. The
application-scoped desktop environment avoids the control center's refusal
when it is launched from a bare SSH session. It changes no session-wide
environment and stores no SIM or APN data in the repository.

The SIPC plugin reports LTE-only software mode support, matching its current
capability and bearer implementation. Previously its inherited `ANY` mode
made GNOME display “2G, 3G, 4G, 5G”. This is not a modem radio-mode command,
does not change RF configuration, and does not establish chipset-wide mode
coverage. Rebuild using `scripts/g965n/build-modemmanager-sipc.sh` and the
verified source archive. The builder requires `patch`, Meson, Ninja and the
documented ModemManager development dependencies. Installing a replacement
plugin must also update the guarded desktop configuration's plugin hash
and its unit's configuration hash; do not bypass the guard.

## Camera and fingerprint

After model/backup verification, the ordinary Ubuntu packages can be
installed separately; no boot image or firmware is written by this step:

```sh
sudo apt-get install --no-install-recommends cheese fprintd
fprintd-list "$USER"
```

On the tested handset Cheese opens but has no camera device. Its attempted
preferences enumeration also emits upstream GLib errors for the missing
device; it was closed after the test. The running kernel has
`CONFIG_MEDIA_SUPPORT` disabled and no `/dev/video*` or `/dev/media*`.
Enabling media configuration alone cannot produce a camera stream: the
Exynos 9810 FIMC-IS ISP, MIPI receiver, sensors, actuators, power/clock and
buffer path must be implemented and tested together. Existing Exynos4
media source is not proof of Exynos9810 ISP support.

The native fprintd manager starts and returns an empty device array;
`fprintd-list` reports `No devices available`. The stock ET510 is a secure
SPI reader, with Samsung biometric and Trustonic dependencies. The running
kernel has no TEE support and no enumerated SPI reader. A transport,
matching secure protocol and libfprint backend are still required before
GNOME Users can offer real fingerprint enrollment. No PAM authentication
change or enrollment bypass was installed. Camera capture and fingerprint
enrollment remain unverified and unavailable on this kernel.

# SM-G965N support package

The `g965n-support` arm64 package installs the board's ALSA UCM profiles, udev
rules, audio timing, display and sleep configuration, and the charging,
thermal, power-key, indicator, vibration and input-boost service code. It uses
the hardware interfaces already provided by the matching kernel and driver
deployment. The device configuration files are dpkg conffiles.

Use the existing BOOT and driver build/deployment procedures first. The
package reuses the guarded driver's module, calibration and pin files from
that deployment. Those artifacts are tied to its kernel and this package
neither installs them nor changes BOOT. In particular, package installation
does not activate the current-boot higher-input or hardware watchdog trials.

Audio, Bluetooth, cover, modem and sensor drivers keep their existing
model/build checks. The sensor drop-in runs the packaged supervisor and
checks the existing root-only sensor profile and fingerprint before startup.
The adoption helper checks that the packaged supervisor matches the profile's
approved digest. The original service supplies its existing hardware
isolation and device allowlist. Site-specific sensor, modem and firmware
inputs and the user's profile remain on the device. Separate Mesa and ModemManager builds
and the Qt sensor plugin retain their existing version requirements.

Build on a Linux host with Python and dpkg:

```sh
python3 scripts/g965n/build-support-deb.py /tmp/g965n-support_1.1.0_arm64.deb
dpkg-deb --info /tmp/g965n-support_1.1.0_arm64.deb
```

On an already configured, backed-up handset, copy the package and installer
from trusted sources and run:

```sh
sudo python3 install-support-deb.py ./g965n-support_1.1.0_arm64.deb \
    --confirm-backed-up-g965n
```

The installer uses the existing device/BOOT/backup guard, archives the old
files, checks runtime helper bytes, and refuses conflicting package ownership
or local changes. Existing enabled units keep their names. Restarting the
phone tests the new entry points without manually unloading active drivers.
For recovery, use the printed tar path. Remove the support package with
`dpkg --purge g965n-support`, then restore the archived files to `/` and reload
systemd. Verify unit enablement against the previous configuration.

Before upgrading Ubuntu packages, record the APT simulation and preserve the
current package versions and configuration. After update and reboot, check
the new boot ID and exact BOOT, run `dpkg --audit` and
`dpkg -V g965n-support`, inspect failed system units and verify the actual
display, Wi-Fi, DRM render device, ALSA playback and capture, IIO consumers, battery/charger and input devices. Test a physical microphone,
screen, sensor movement, NFC tag or cellular data separately when applicable.
See [VALIDATION.md](VALIDATION.md) for results and limitations.

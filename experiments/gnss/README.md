# G965N standalone GNSS probe

`hal-probe.c` calls the handset's legacy Android GNSS HAL through its
published LP64 callback ABI. It requests standalone mode with one-second
updates, waits for 24 seconds by default (or 1–240 seconds as requested),
and stops and cleans up. The default reports counts and status codes.
It does not record coordinates or NMEA strings. Passing `90 --nmea-fd3`
streams checksum-validated NMEA through a private pipe already open on
file descriptor 3. NMEA may contain coordinates on a successful fix.

The interface layouts follow [AOSP Android 10 gps.h](https://android.googlesource.com/platform/hardware/libhardware/+/android-10.0.0_r47/include/hardware/gps.h).
The executable startup uses the Android 10 [Bionic startup ABI](https://android.googlesource.com/platform/bionic/+/android-10.0.0_r47/libc/arch-common/bionic/crtbegin.c).
Build against private, read-only copies of the owner's Bionic DSOs. These
libraries and the Samsung HAL are not included. For example, on AArch64
Ubuntu with GCC:

```sh
gcc -O2 -fPIE -pie -fno-stack-protector -mno-outline-atomics \
  -U_FORTIFY_SOURCE -nostdlib -Wl,-e,_start \
  -Wl,--dynamic-linker=/system/bin/linker64 -Wl,--allow-shlib-undefined \
  hal-probe.c "$BIONIC_LIBS/libc.so" "$BIONIC_LIBS/libdl.so" -o hal-probe
```

Running requires an explicitly authorized, verified SM-G965N with the
sensor hub already active. Run under the handset's Android linker in
an isolated mount, PID and network namespace, with read-only
SYSTEM/VENDOR/Android runtime, no identity, radio or block devices,
and bounded private scratch data. For a live trial, hold the shared sensor
runtime lease and use the hub's dedicated GPS IPC directory. Launch the
own-vendor GPS daemon with its own GNSS configuration in the same trial.
Use a process timeout and stop both processes before releasing the lease.

`nmea-relay.py` is the bounded trial relay. Give it a private root-owned
runtime directory containing a root-only FIFO named `nmea.fifo`, followed
by the numeric GeoClue UID. It creates a local `nmea.sock` and accepts
only that peer UID. Connect the test consumer before starting the producer,
and remove the trial runtime after both exit. The relay keeps no NMEA log.

Native #47 delivered real checksum-valid GGA, RMC, GSA and vendor messages
to the GeoClue account. A successful HAL `start()` or raw NMEA reception
does not prove a position fix. Configuring GeoClue's
[local NMEA socket](https://manpages.ubuntu.com/manpages/noble/man5/geoclue.5.html)
does not grant desktop applications access when user location services
are disabled.

## Start GPS on demand from GeoClue

On a handset with the exact guarded sensor profile and independent recovery
backup verified, install the built helper as `/usr/local/lib/g965n-gnss/hal`
and install `serve.py` alongside it. Keep that directory root-owned and
mode 0700. Write `pins.json` there with the SHA-256 of the executable
(`hal`), the handset's read-only `vendor/bin/hw/gpsd` (`vendor_daemon`),
and `vendor/etc/gnss/gps.xml` (`vendor_config`). These paths are relative
to `/run/g965n-sensor-runtime/root` for the vendor inputs. The supervisor
rechecks the active sensor profile and BOOT before opening the hardware
path.

Install the supplied socket and service under `/etc/systemd/system`. Put
the following in `/etc/geoclue/conf.d/80-g965n-gnss.conf`:

```ini
[network-nmea]
enable=true
nmea-socket=/run/g965n-gnss/nmea.sock
```

Run `systemctl daemon-reload` and `systemctl enable --now g965n-gnss.socket`.
Restart an active GeoClue to read its new source. The socket accepts only
the GeoClue service account. The worker uses an isolated vendor runtime,
and stops its GNSS session when GeoClue disconnects. Other GeoClue sources
and desktop application permissions continue to use Ubuntu's settings.

## UTC assistance

The daemon still uses standalone mode. When Ubuntu's per-boot time-sync
marker is present and timedated reports NTP synchronization, the
supervisor passes `--inject-current-utc` to the HAL helper. The helper
samples UTC and Android's elapsed-realtime equivalent (Linux
`CLOCK_BOOTTIME`) and calls the existing Android `inject_time` method.
If synchronization is unavailable, standalone startup continues as
before. The journal records only the HAL return code, without a time
value or NMEA content.

This provides a time reference. The later LTO assistance path is described
below; prior-position injection remains unimplemented. A return code of zero acknowledges the input. A valid NMEA fix
and a GeoClue location callback remain the criteria for position
verification.

## Wi-Fi testing and desktop applications

USB is not required by this runtime. Use an already authenticated SSH
connection to the handset's **Wi-Fi** address, maintain that Wi-Fi connection,
and place the phone where it has sky exposure. Keep the key/address in local
connection configuration, not in this repository. The owner reported USB
removed for the 2026-11-20 trial; the gadget's UDC state still said configured,
so that sysfs field alone is not proof of cable presence or removal. The actual
SSH destination and explicitly Wi-Fi-bound HTTPS check establish that this
test does not depend on the USB network.

`check-fix.py` connects as GeoClue to the guarded GNSS socket and reports
checksummed sentence counts, satellites used/in view when reported, and fix
presence. It never prints or retains coordinates or NMEA. Exit 2 means no fix
was observed; a successful test-program run does not establish GPS support.

After exact-model/BOOT/backup verification, the manual app setup on the
handset is:

```sh
sudo apt-get install --no-install-recommends gnome-startup-applications gnome-maps
sudo install -d -m 0755 /usr/local/share/g965n-gps-test
sudo install -m 0644 check-fix.py test-app.py /usr/local/share/g965n-gps-test/
sudo install -m 0644 g965n-gps-test.service /etc/systemd/system/
sudo install -m 0644 g965n-gps-test.desktop /usr/local/share/applications/
# Select the actual authorized desktop account, not a group or wildcard.
DESKTOP_USER=ubuntu
sed "s/@DESKTOP_USER@/$DESKTOP_USER/g" 49-g965n-gps-test.rules.in |
  sudo tee /etc/polkit-1/rules.d/49-g965n-gps-test.rules >/dev/null
sudo chmod 0644 /etc/polkit-1/rules.d/49-g965n-gps-test.rules
sudo systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/g965n-gps-test.service
desktop-file-validate /usr/local/share/applications/g965n-gps-test.desktop
```

Run those copy steps from this directory on the phone. The frontend uses the
normal desktop account. The narrowly scoped Polkit rule permits only that
account, including its authenticated SSH sessions, to start/stop this exact
bounded test unit. It grants no generic unit management. The unit runs as
GeoClue, has no network address family except AF_UNIX, and reads only the
existing checked GNSS source. Its public summary contains counts and a fix
boolean, with no location. The root-owned HAL supervisor still enforces the
device/profile/firmware guards. Nothing is enabled to test automatically at
login or boot.

Open **GPS 수신 시험 / GPS Test** in the app list. Alternatively, from the
selected account over Wi-Fi:

```sh
systemctl start g965n-gps-test.service
cat /run/g965n-gps-test/summary.json
systemctl stop g965n-gps-test.service
```

The five-minute test releases its source at the end or after cancellation.
The source socket accepts only one session, so avoid requesting Maps' live
location during the raw test. GNOME Maps may show a network-derived position;
that is not evidence of a satellite fix. GPS Test distinguishes live and old
summaries, and an absent GSV report means satellite visibility is unknown.
The startup manager controls ordinary login applications; hardware systemd
services remain separate.

The initial wireless 300-second test delivered 14 valid sentences, no invalid
checksums, GSA fix type 1, zero used satellites and no valid GGA/RMC fix.
The daemon crash correction below supersedes the continuous-update failure.
The later opened-window trial below established a real position fix.

## Remaining assistance work

Android can download predicted satellite data and inject it into its GNSS
HAL; see the primary
[AOSP GNSS provider](https://android.googlesource.com/platform/frameworks/base/+/master/services/core/java/com/android/server/location/gnss/GnssLocationProvider.java).
The HAL exposes gps-xtra, agps, agps_ril, gps-debug and gnss_configuration.
The port now implements synchronized UTC and the bounded LTO cache below.
SUPL sessions and prior-position injection remain unimplemented. The vendor
worker retains its isolated network namespace.

## Android sensor-service crash correction

Native debugging located a null dereference in the vendor daemon's
`NdkSensorsInfo`, called by `NdkSensorsStart` from its sensor thread. This
Android HIDL service is absent on Ubuntu. The supervisor formerly waited on
the still-running HAL pipe and did not notice the daemon's exit, making it
look like an acquisition wait. `watch_hal` now checks both processes and
cleans up the remaining client when the daemon exits.

The supervisor creates a private copy of the pinned owner configuration and
changes only its `hal SensorsEnable` attribute to false. Samsung's published
[Broadcom GPS configuration](https://android.googlesource.com/device/samsung/manta/+/refs/heads/jb-mr1-dev/gps/gps.xml)
documents this option, and the owner's daemon contains the matching setting.
The binary, original vendor configuration, RF values and main Ubuntu sensor
services stay intact. Optional Android-sensor inertial assistance is disabled.
The resulting first 300-second native trial delivered 3,291 valid NMEA sentences
with zero invalid checksums, rather than stopping at 14. That initial window
trial had no fix; the later reception trial below did.

Diagnostic HAL status is restricted to numeric counters and named capability
availability. `G965N_GNSS_DIAGNOSTICS=1` optionally starts a private Android log
socket with a strict error filter: location/identity messages are discarded and
numbers/URLs redacted. It is disabled by default. Never commit raw crash logs.

## Qualified-source LTO cache and HAL delivery

`assistance.py` reads the owner's read-only SYSTEM `etc/gps_psds.conf` and
accepts only its configured Broadcom `/4day/v5/latest/lto2.dat` sources. It
upgrades their transport to certificate-validated HTTPS, bounds the download
to 512 KiB, rejects HTML, and verifies the server Last-Modified age is under
four days. Root-only cache metadata pins the source, input configuration and
blob SHA-256, with a 24-hour reuse limit. Tampered/stale/mismatched data is not
passed to the HAL. No receiver firmware is flashed and no downloaded blob is
redistributed. The current source returned a fresh 124,383-byte file.

After the model/BOOT/backup checks, preserve the previous HAL/supervisor/pins,
build the updated `hal-probe.c` using the same own-Bionic procedure above,
install it and update `pins.json`'s `hal` hash. Install the updated `serve.py`
and the following additional files as root on the handset:

```sh
sudo install -m 0600 assistance.py /usr/local/lib/g965n-gnss/assistance.py
sudo install -m 0644 g965n-gnss-assistance.service g965n-gnss-assistance.timer \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start g965n-gnss-assistance.service
sudo systemctl enable --now g965n-gnss-assistance.timer
```

The timer checks freshness hourly; fresh data is reused without a download.
Unavailable networks do not disable standalone GNSS. Cache files live under
`/var/lib/g965n-gnss-assistance` with owner root and mode 0700/0600. Downloads
run outside the receiver's network namespace; that isolation is retained.
The supervisor rechecks cache integrity and passes an already open read-only
file on FD4 to the HAL's standard gps-xtra API, separate from FD3 NMEA output.
XTRA init and injection returned zero, and the receiver's stored `lto2.dat`
matched the downloaded cache hash. This proves delivery/storage, not a position
fix or a measured time-to-first-fix improvement. A downloaded file for a
different receiver is not a substitute for the qualified own-device source.

## Physical fix and standard desktop delivery

The owner offered to open the window for the next wireless trial. Its
300-second summary had 4,448 valid sentences, zero invalid checksums, a real
GGA/RMC fix and GSA 3D state. GSV reported up to ten satellites in an individual
constellation and GGA up to eight used satellites. This GSV maximum is not the
sum across all constellations. No coordinates were printed or committed.

`geoclue-check.py` creates a genuine desktop GeoClue client under the installed
GPS Test desktop ID. It reads only location existence, timestamp and accuracy;
it never reads latitude/longitude. After the raw test released the singleton
source, this client received a fresh location (1.2 seconds old, reported
accuracy 3 m). That accuracy is the receiver/service estimate, not a surveyed
error measurement. GNOME Maps' native current-location action was activated
and no connection/location-disabled error was visible. Map centering ground
truth, navigation and long-term accuracy were not qualified.

For a reproducible desktop check, after the device/profile checks install:

```sh
sudo install -m 0644 geoclue-check.py /usr/local/share/g965n-gps-test/
DESKTOP_UID=$(id -u ubuntu)
sed "s/@DESKTOP_UID@/$DESKTOP_UID/g" 90-g965n-gps-test.conf.in |
  sudo tee /etc/geoclue/conf.d/90-g965n-gps-test.conf >/dev/null
sudo systemctl restart geoclue
python3 /usr/local/share/g965n-gps-test/geoclue-check.py --seconds 90
```

Run the last command as the selected desktop account. The permission is scoped
to this diagnostic ID and UID. This check shares GeoClue's source with Maps;
do not run the direct NMEA GPS Test unit at the same time. Keep normal location
preferences enabled. Cold reboot, suspend/resume, moving outdoor accuracy and
the real effect of assistance expiry remain separate hardware regressions.

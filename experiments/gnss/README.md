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

This provides a time reference. Satellite ephemeris, a network
assistance service and a persistent position cache are outside this
path. A return code of zero acknowledges the input. A valid NMEA fix
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

The wireless 300-second test delivered 14 valid sentences, no invalid
checksums, GSA fix type 1, zero used satellites and no valid GGA/RMC fix.
Continuous receiver updates and position acquisition remain open.

## Remaining assistance work

Android can download predicted satellite data and inject it into its GNSS
HAL; see the primary
[AOSP GNSS provider](https://android.googlesource.com/platform/frameworks/base/+/master/services/core/java/com/android/server/location/gnss/GnssLocationProvider.java).
The current port implements only synchronized UTC injection. It does not yet
download SUPL/PSDS/LTO assistance or inject a prior position, and the vendor
worker intentionally has an isolated network namespace. Ubuntu can support
these functions when the hardware backend supplies them. The next work is to
inventory the actual Broadcom HAL extensions and own-device configuration,
then implement a compatible, bounded assistance path with expiry and error
handling. A downloaded file for another receiver is not a valid substitute.
Do not attribute the observed lack of continuous samples solely to missing
assistance; IPC, receiver state and RF acquisition still require investigation.

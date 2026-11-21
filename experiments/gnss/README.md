# G965N standalone GNSS probe

`hal-probe.c` calls the handset's legacy Android GNSS HAL through its
published LP64 callback ABI. It requests standalone mode with one-second
updates, waits for 24 seconds by default (or 1–240 seconds as requested),
and stops and cleans up. The default reports counts and status codes.
It does not record coordinates or NMEA strings. Passing `90 --nmea-fd3`
streams checksum-validated NMEA through a private pipe already open on
file descriptor 3. NMEA may contain coordinates on a successful fix.

The legacy interface prefix follows [AOSP Android 10 gps.h](https://android.googlesource.com/platform/hardware/libhardware/+/android-10.0.0_r47/include/hardware/gps.h).
This handset additionally calls a two-boolean location-request callback after
the96-byte callback prefix. The own-device extension is explicit, with a
compile-time offset check and persistent callback storage; it is not a claim
that the upstream legacy GpsCallbacks has this field. The handler only records
requests, never reenters GeoClue or reuses GNSS output as an independent
network-location reply. Its semantics correspond to the separate
[AOSP location request contract](https://android.googlesource.com/platform/hardware/interfaces/+/27178421050682d91f1da59a96092cbea673a547/gnss/aidl/android/hardware/gnss/IGnssCallback.aidl).
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

## xgps satellite diagnostic viewer

`xgps-bridge.py` and `xgps-launch.py` are GPL-2.0-only integration helpers.
Install Ubuntu `gpsd-clients` and `gpsd` (no firmware redistribution). After
model/current BOOT/protected-backup checks, privately back up installed serve.py.
Install this revision of serve.py and xgps-bridge.py in the existing root-private
GNSS directory. Install xgps-launch.py as executable /usr/local/bin/g965n-xgps;
install g965n-xgps.service separately and enable/start it. Builds never install
or flash these files. Retain original permissions and the GeoClue-only peer ACL.

The updated serve.py copies received NMEA to a nonblocking root-private datagram
socket; a missing/slow viewer cannot block GeoClue. The bridge accepts only root
sender credentials, feeds a private PTY and starts stock GPSD on loopback port2948.
GPSD -b disables receiver probing; all PTY output is discarded, so viewer
commands cannot reach the vendor HAL. Raw NMEA/coordinates are never logged.
Local GPSD clients can read location when the authorized location session is
active; port2948 must remain loopback-only. No remote TCP listener is required.

Authorize desktop ID g965n-xgps for the intended desktop UID in a GeoClue
conf.d file (allowed=true, system=false, users=<desktop UID>). Its application
launcher runs /usr/local/bin/g965n-xgps as that ordinary user. The wrapper holds
an authorized GeoClue client only while xgps runs, respecting desktop location
permission. Restart GeoClue once to read the new source/helper and application
policy; do not connect a diagnostic directly to its restricted NMEA socket.

Native48 installation: stock packages3.25-3ubuntu3.2 installed; ordinary-user
window launched. Live receiver NMEA and GPSD TPV messages reached the viewer
backend after initial receiver startup delay. Satellite availability/fix depend
on reception; this is not a new outdoor accuracy qualification. Root-only
rollback copy retained. To remove integration, close the viewer, stop/disable
only g965n-xgps, restore previous serve.py, remove the owned launcher/application
policy and restart GeoClue. Preserve existing GNSS/sensor configuration.

The installed menu uses a per-user xgps.desktop override pointing to the
connected wrapper; the stock package launcher is preserved. Final connected
port2948 window verified via accessibility and145 live TPV records received,
mode1 (no fix). A bridge restart disconnects existing xgps clients; reopen
the viewer afterward. New bridge startup after a reboot remains untested.


### Location review observation

Run `gpsd-summary.py --seconds 180` as the authorized desktop user. It holds its own GeoClue request: watching GPSD
alone does not keep the on-demand receiver running. It prints only counters,
fix modes, NMEA types and aggregate GSV/CN0 values, never raw positions or IDs.
HAL standalone-mode/start numeric status now passes the existing strict status
log filter. Window-only tests received valid NMEA but had0 satellites/mode1;
open-sky reproduction is pending. See LOCATION_REVIEW.md for exact limits.

## Start-position assistance and private previous-fix cache

`seed.py` implements host-side assistance, not a new GeoClue location provider.
It respects the ubuntu desktop location switch. First it considers the private
previous real GPS fix and network estimate; otherwise it makes one bounded
HTTPS BeaconDB lookup using existing ModemManager LTE cell records, permitting
IP fallback. No crowdsourcing/submission is performed. This query sends cell
identities to the configured fixed HTTPS provider; it never logs those identities,
coordinates or raw responses. Redirects are rejected. A cell-only diagnostic
(`sudo python3 /usr/local/lib/g965n-gnss/seed.py --cell-only`) prints only status
and accuracy, and never silently enables IP fallback.

Root-only `/var/lib/g965n-gnss-seed` (0700) contains at most `network.json` and
`gnss.json` (0600). Network estimates remain distinct from real GNSS fixes.
Only fresh timestamped GPSD TPV mode2/3 with valid coordinates/uncertainty enters
the GNSS cache; watching GPSD alone does not activate the receiver. Seeds expire
after300s, gain350m uncertainty per second of age and are rejected above100km.
That travel allowance is deliberately conservative and is not a model of actual
movement. Old files can remain privately stored but cannot be reused after
expiry. Delete only this private cache directory to erase remembered positions,
with the cache service stopped. Never publish it or include it in an image.

`serve.py` passes a validated text seed through inherited read-only FD5; no
coordinates enter command-line arguments or journal messages. The HAL helper
revalidates finite values, age and accuracy before calling standard
[GpsInterface.inject_location](https://source.android.com/reference/hal/struct_gps_interface).
This is an approximate starting location, not satellite-derived output. Failure
of optional assistance leaves standalone GNSS available. A cache miss can add
bounded lookup latency (MM calls2s/2.5s, HTTPS socket timeout3s); end-to-end TTFF
benefit is unqualified. A cached seed avoids that network lookup.

Build the updated own C helper with the command at the top of this document;
building never installs or flashes. Before separate deployment verify the model,
current BOOT, protected backups and original HAL pin. Privately snapshot the
installed `hal`, `pins.json`, `serve.py`, and any preexisting `seed.py`. Install
own `hal`0500, `serve.py`/`seed.py`0600 in the existing0700 root GNSS directory,
and update **only** the HAL SHA-256 field of existing private pins.json0600.
Preserve the vendor input pins. Install `g965n-gnss-seed-cache.service`0644,
daemon-reload, enable/start it and restart GeoClue once. Keep normal peer ACLs,
network/PID/mount isolation and existing sensor/firmware configuration.

The cache watcher reads only loopback GPSD2948, does not request a GeoClue session
or start RF, and saves at most once per10s when location is enabled. Rollback:
stop GeoClue and GNSS sessions, disable/stop only the seed cache service, restore
the privately backed-up HAL/pins/supervisor/helper, remove only the owned unit,
daemon-reload, restart the original GNSS socket/GeoClue. Preserve XTRA, sensors
and user configuration. Never remove unknown GPS state while an owner is active.
Current device qualification and negative controls are recorded in
[LOCATION_REVIEW.md](../../docs/g965n/LOCATION_REVIEW.md).

### Remaining assistance work

UTC and LTO/XTRA are connected already. This seed/cache layer supplies an
additional input; it does not implement SUPL. The vendor exposes `agps` and
`agps_ril`, but extensions being present is not proof of an operating session.
[AOSP AGpsInterface](https://source.android.com/reference/hal/struct_a_gps_interface)
requires initialization/status callbacks and data connection open/closed/failed
lifecycle, not just a server hostname. The current vendor process has an
isolated network namespace. A future SUPL bridge needs qualified callback ABI,
connection/TLS/server support and a narrowly constrained transport; removing
network isolation globally is not an acceptable shortcut. Integration belongs
between the host connection manager and vendor HAL, below GeoClue's public app
API. Do not change the kernel unless evidence locates a failure there.

Then compare actual open-sky cold/warm TTFF with/without assistance, offline and
expired cache, first-fix versus IP estimate, and suspend/reboot recovery. The current S9+ no-satellite result cannot qualify Android-equivalent speed.
The owner subsequently confirmed an actual Android satellite fix at the same
place, so a location-only explanation has been withdrawn.

Native48 qualification: corrected callback handled an actual request without
exception;180s delivered1688 NMEA/1225 TPV. After a clean session shutdown and
ordinary warm reboot, exact model/BOOT/protected-backup/HAL pin checks passed;
sensor/socket/GPSD bridge/cache units auto-started. A further91s delivered687
NMEA/498 TPV with one request callback and numeric start/UTC/position/XTRA0.
These no-satellite/mode1 observations qualify the assistance/transport and
reboot path, not a new position fix or improved TTFF. The network cache expired
correctly and never populated the separate genuine-GNSS cache; capture/reuse
of that real-fix cache remains a favorable-reception hardware test.


## Same-place RF comparison and request-driven aid (2026-11-21)

The owner confirmed another Android GPS diagnostic obtains a real satellite
fix at the same place. A subsequent photo directly shows4 signals,2 marked
in use and about21–27 signal strength, while status is No Fix. That photo
proves signal reception, not a completed fix at that instant. Earlier
environment-only interpretations are superseded.
SM-G965N still delivered0sat/mode1 after300s2996 NMEA/2177 TPV. Transport is
alive; this does not qualify RF reception or Android-equivalent assistance.

The HAL now services asynchronous location requests on the main control loop,
using only the already prepared **network** seed as an independent reply.
The callback thread only increments a counter. A private seed-independent
marker causes the host to pass --seed-independent; a previous-GNSS cache never
gets that flag. FD5 is rewound for each request. The host passes original sample
accuracy/timestamp and the C helper adds350m/s at injection, avoiding double
ageing while rejecting expired/excessively uncertain input. The location reply
was actually exercised (two inject0 responses/request replay1), but301s3018
NMEA/2193 TPV still had no satellites/fix.

A temporary UTC/XTRA callback-response candidate observed0/0 requests and
181s1699 NMEA/1233 TPV without fix; those request paths were not exercised by
the handset. Another candidate replayed UTC/XTRA once after first NMEA, with
one XTRA initialization and two successful inject calls, but receiver state
and181s1698 NMEA/1232 TPV did not improve. These timing/UTC/XTRA candidates were
removed; the actually exercised network-only request reply remains installed.
Do not add repeated aid injection as a presumed fix. Dynamic time/ephemeris
consumption still needs diagnosis.

`receiver-status.py` is a read-only loopback GPSD observer. Open the authorized
xgps viewer, or run gpsd-summary.py as the authorized desktop user in another
terminal, then run:

```sh
python3 receiver-status.py --seconds 60
```

It does not activate RF or grant a new GeoClue policy. It emits only checksum-
checked PGLOR type counts and selected nonlocation STA aggregate fields. It
never emits NMEA, coordinates, UTC timestamps, cell/satellite IDs or arbitrary
payload. Invalid/unknown layouts are not decoded. On this handset version9
STA matched the common marker layout: aid tPeF, ephemeris0, prefix fields4..9
0/4294.967/0/2000/9999/0, full-power code F. Aiding-state interpretation is
inferred from the same chipset supplier's published
[LC29D protocol, STA](https://quectel.com/content/uploads/2024/02/Quectel_LC29D_GNSS_Protocol_Specification_V1.0-1.pdf)
(version10), not independently qualified Samsung version9 semantics. In that
reference time/ephemeris aid are unavailable for lowercase t/e; API return0
must not be presented as proof of receiver consumption or a GPS fix.

Filtered diagnostic logging exposed optional trace-directory and RIL connection
refusal messages; neither has been proved the RF cause. Temporary logger drop-in
was removed and its process stopped. No kernel/clock/regulator/GPIO/firmware
change was made. Existing kernel lacks KPROBES/FTRACE/BPF_EVENTS, so kernel
packet-level instrumentation was not available. Static inspection of mixed
sensor/GNSS routing suggests a possible drop condition, but real mixed packets
were not observed; no speculative driver fix was installed. USB remains connected because the owner cannot disconnect it now; that
comparison and a direct RF/assistance-consumption diagnosis remain open.


File-metadata tracing was inconclusive: supervisor tracing captured validation,
then interrupted startup left known trial state and a later direct-GPSD attach
found no daemon. Neither handshake-only run is RF evidence. All tracers were
detached; after stopped source units/no vendor process/exclusive GNSS lease,
five known artifacts were privately preserved before resuming the checked
network-reply baseline. Do not delete unknown state or claim a file/permission
root cause from this attempt.

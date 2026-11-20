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

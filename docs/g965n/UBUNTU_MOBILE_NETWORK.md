# Ubuntu mobile networking on the SM-G965N

The Exynos SM-G965N uses Samsung SIPC. The desktop adapter shares the
existing RIL control socket and gives ModemManager the modem's IPv4
configuration. The modem driver exposes the physical `rmnet0` data port
when loaded with `link_wwan_parent=1`.

## Build

Use Ubuntu Noble's `modemmanager_1.23.4.orig.tar.gz` from the
[Ubuntu archive](https://archive.ubuntu.com/ubuntu/pool/main/m/modemmanager/).
The build script verifies the archive SHA-256 recorded by
[Ubuntu's 1.23.4-0ubuntu2 source package](https://launchpad.net/ubuntu/+source/modemmanager/1.23.4-0ubuntu2).
The tarball and its licensing notices remain upstream. The repository
contains the reviewed source differences and the SIPC plugin. The test
bundle uses the pinned upstream tarball with the included patch.

On an Ubuntu build host, install a C toolchain, Bash, coreutils, tar, patch,
Meson, Ninja, pkg-config, gettext, xsltproc and development packages for
GLib, D-Bus, GUdev, polkit, systemd and json-glib. For a cross-build, supply
a Meson cross file that selects an AArch64 C toolchain and the ARM64
pkg-config directories.

```bash
scripts/g965n/build-modemmanager-sipc.sh modemmanager_1.23.4.orig.tar.gz out-mm-sipc
```

Use a new output directory. The runnable test bundle is under
`out-mm-sipc/bundle`. The build script does no device operations.

## Verified on the handset

A private D-Bus session ran the ARM64 manager on the native44 kernel,
alongside the Ubuntu-installed manager. The trial scoped discovery to
the actual physical `rmnet0` with temporary udev metadata in an isolated
mount namespace. The trial RIL checked the exact device, module, BOOT
image and private runtime provenance before powering the modem. The
manager reported that data port and a SIM object based on confirmed
modem readiness, without assigning invented SIM identifiers.

`Modem.Enable` and `Modem.Simple.Connect` succeeded. The returned IPv4
bearer was on `rmnet0`. A separate guarded source-route probe over that
bearer passed modem DNS and certificate-verified HTTPS204 and removed
its temporary network configuration. ModemManager's
`Bearer.Disconnect` returned success after the RIL verified release
and withdrew the lease. Wi-Fi's default route and the sensor service
survived the trial.

The trial used an explicitly supplied IPv4 APN matching the running RIL.
Legacy generic AT callbacks reported unavailable serial ports.

## Verified with the system NetworkManager

A separate bounded native44 trial temporarily ran the reproduced
ARM64 bundle as the system ModemManager. A runtime service override
scoped discovery to the physical modem inside the daemon mount
namespace and was removed after the test. The existing Ubuntu
NetworkManager activated a temporary GSM profile through that manager.
NetworkManager installed an IPv4 default over `rmnet0` at metric
20000, while Wi-Fi kept its preferred route. DNS and certificate-verified
HTTPS204 passed over sockets bound to the LTE interface and address,
using the routes installed by NetworkManager.

NetworkManager deactivated the profile and removed the LTE route,
and the RIL confirmed release and withdrew the lease. The temporary
profile was deleted and the stock manager restored. The original Wi-Fi
default remained in place. This qualifies the tested system handoff.
The bounded trials do not qualify SIM PIN, SIM hot swap, calls or SMS.

## Verified after boot and through the system mobile-data switch

An armed one-shot systemd service started the native44 trial on a
distinct reboot. It disabled itself as it began and started LTE
through the existing NetworkManager. Two writes of
`WwanEnabled=false` removed the LTE route and its modem lease. Setting
`WwanEnabled=true` between them automatically reactivated the temporary
GSM profile without a separate connection command. Both data
generations passed LTE-bound DNS and certificate-verified HTTPS204.
The second passed again 30 seconds later. Wi-Fi stayed the preferred
route while mobile data was active.

The service restored the original ModemManager and WWAN switch setting
and removed the temporary profile. This verifies the NetworkManager
switch path and one-shot boot startup. Direct GNOME interaction and
continuous mobile service across ordinary boots remain pending.

## Supervisor-owned lifetime

The launcher accepts `--service-lifetime` for the isolated,
lease-backed desktop bearer path when `g965n-desktop-lte.service`
is active. The RIL and CBD children bind to that unit instead of
using the lab duration. This mode rejects lab tracing, diagnostic
capture and the 300-second soak mode.

In a guarded native44 trial, the same RIL invocation, CBD and
NetworkManager bearer passed LTE-bound DNS and HTTPS204 at 0.7,
90.6 and 306.5 seconds after connection. The test supervisor
disconnects the temporary profile and restores the stock manager.
This verifies over five minutes without the child deadline.

## Opt-in desktop service

`scripts/g965n/desktop-lte-service.py` is the supervisor for the
`g965n-desktop-lte.service.in` template in `scripts/g965n/units`.
Its configuration is a root-private `config.json` under
`/var/lib/g965n-lte/<name>`. The service uses the verified native44
kernel and backup receipts, a physical-port SIPC module and the
ARM64 test bundle. Build and review those artifacts first.

The configuration holds `model`, `apn`, `auto_profile`,
`kernel_profile`, `guard_sha256`, `receipt_sha256`,
`backup_sha256` and `files`. The model is `SM-G965N`, the APN
must match the provisioned SIM, and `auto_profile` is a boolean.
The three receipt digests cover the device's own reviewed guard,
startup receipt and backup receipt. The `files` object maps each of
the supervisor's required relative paths to its SHA-256. Copy
`ril-lab.py` and `rfs-copy.py` from `experiments/modem`. Copy
`modem/g965n-modem.ko` from the verified physical-port build and
the `mm/` files from the ARM64 bundle. The other scripts come from
`scripts/g965n`.

Render the unit with the approved directory and the digest of its
`config.json`. The directory, files and activation marker
`enabled` must be root-owned, with the directory private to root.
After verifying the model, backup and running BOOT, install and
verify the rendered unit. Enabling it before a reboot opts in to
desktop LTE on that boot. With `auto_profile=true`, the service
supplies a temporary GSM profile with an IPv4 route metric of 20000.
NetworkManager owns the routes and honors the saved WWAN setting.

On normal service stop, the temporary profile and service override
are removed and the installed ModemManager returns. If the modem
module is still resident, the next clean boot starts the service
with a fresh modem session. The build script does no device setup
and leaves the service opt-in.

On the native44 handset, the persistent service automatically
connected on two distinct ordinary boots. LTE-bound DNS and HTTPS204
passed on both while Wi-Fi retained the preferred default. Between
them, an explicit service stop confirmed modem bearer release and
radio low power, removed the LTE route and restored the stock manager.
The matched service is enabled on the test handset.

A separate test killed only the desktop supervisor while its LTE
bearer was active. The systemd stop hook rechecked the pinned
configuration and cleaned the owned profile, modem runtime and
invocation files. The children stopped, the modem confirmed release
and radio low power, and the original ModemManager returned while
Wi-Fi stayed usable. The enabled service starts a fresh session
on the next clean boot. Direct GNOME interaction, unexpected radio
loss and additional hardware remain unqualified.

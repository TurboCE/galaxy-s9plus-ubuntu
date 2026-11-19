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
The GNOME settings interaction and persistent mobile service remain
pending. The bounded trials do not qualify SIM PIN, SIM hot swap,
calls or SMS.

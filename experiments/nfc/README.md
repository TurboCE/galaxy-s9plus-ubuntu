# SM-G965N NFC I²C transport trial

This is the device-tree change used to register both NFC-related I²C
controllers on native #48. It intentionally leaves both buses without
kernel I²C clients. The handset's own revision 26 stock BOOT matched
both controller resources and pin groups.

| Controller | Stock client | Pin group |
|---|---|---|
| 0x108e0000, full USI08 | S3NRN82 at 0x27 | GPP5 lines 0 and 1 |
| 0x10930000, dedicated USI10 I²C | PCAL6524 at 0x22 | GPP6 lines 2 and 3 |

Use the already patched native #48 kernel source and output directory.
The patch changes the S9+ inner device tree.

```sh
git -C "$KERNEL_SOURCE" apply --check "$PROJECT/experiments/nfc/peric1-i2c-trial.patch"
git -C "$KERNEL_SOURCE" apply "$PROJECT/experiments/nfc/peric1-i2c-trial.patch"
make -C "$KERNEL_SOURCE" O="$KERNEL_OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  exynos/exynos9810-star2lte.dtb
```

Package the result with the same Linux Image in uniLoader. Check the
model, obtain consent and verify a fresh recovery backup before any
separate BOOT-only deployment. Build commands never write the phone.

Both controllers bound to `exynos5-hsi2c` and produced a Linux bus.
A targeted PCAL6524 read timed out while the legacy Bluetooth module
used the same GPP6 pins through its GPIO I²C bus. Temporarily setting
the dedicated controller's clock-request bit did not resolve the
timeout. The original value was restored. With Bluetooth stopped and
the dedicated pins restored to their I²C mux, the PCAL6524 returned an
input-register byte. Concurrent use still requires a single expander
owner and a Bluetooth GPIO consumer.

The trial uses a 200 MHz nominal clock for both controllers. Readback
of the running clock selection and dividers implies 50 MHz for full
USI08 and 200 MHz for dedicated USI10. Validate the inherited clock
tree before attaching clients or treating the indicated SCL as a
physical measurement. The expander reset and supply, the NFC power
sequence and the native NFC protocol path remain unqualified.

- [LineageOS revision 26 device tree](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts)
- [LineageOS Exynos9810 clock register table](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/drivers/soc/samsung/cal-if/exynos9810/cmucal-sfr.c)

## Share the expander with Bluetooth

The legacy Bluetooth path owns GPP6 through a separate GPIO I²C
adapter. The `native_expander=1` option of `zrn-bt.ko` instead uses
line 7 of the PCAL6524 handled by the standard `gpio-pca953x` driver
on the native controller. The module checks the exact controller
path and the type and driver of its client. The default Bluetooth
option still uses the legacy startup path.

On the native #48 bus trial, the PCAL6524 and Bluetooth were tested
together using the standard GPIO driver, a temporary I²C client and
a guarded local module load. This arrangement is not yet described
by the boot device tree or by the installed startup unit. A native
startup configuration must instantiate the expander before loading
Bluetooth. It must not run the legacy GPIO I²C client in parallel.

## Linux NFC core

The trial used the existing kernel with the upstream NFC and NCI
modules compiled for its exact release. For a fresh kernel build,
enable `CONFIG_NFC=m` and `CONFIG_NFC_NCI=m` and build the modules
against that kernel's complete symbol table. On the handset both
the AF_NFC socket interface and the `nfc` generic netlink family
worked. An NFC radio must still bind before an application can poll
or read tags.

[Linux NFC userspace interface](https://docs.kernel.org/networking/nfc.html)

## Start the shared configuration at boot

On the verified #48 NFC-bus BOOT, install `start-shared.py` and the
matching `zrn-bt.ko`, `nfc.ko`, `nci.ko` and `g965n-s3nrn82.ko` in a root-owned private
directory such as `/usr/local/lib/g965n-native-nfc`. Place the four
module SHA-256 digests in `pins.json` using keys `zrn-bt`, `nfc`,
`nci` and `g965n-s3nrn82`. Retain the original `g965n-bluetooth.service` BOOT/package
verification command when overriding the legacy module load.

The tested systemd service drop-in clears `ExecStartPre` and re-adds
that existing verifier. It clears `ExecStart`, then uses these settings.

```ini
ExecStart=/usr/bin/python3 /usr/local/lib/g965n-native-nfc/start-shared.py start
ExecStopPost=/usr/bin/python3 /usr/local/lib/g965n-native-nfc/start-shared.py stop
RuntimeDirectory=g965n-native-nfc
RuntimeDirectoryMode=0700
```

The helper instantiates the sole expander client, verifies the native
driver, loads the pinned modules and locates the actual Bluetooth UART.
The stop hook removes only the Bluetooth module loaded by that service.
The expander and NFC core stay available to other consumers. A normal
reboot verified this setup. The corrected controller driver registers a standard NFC radio after
a successful CORE_RESET response. The board's VEN is active-low,
as defined by SEC_NFC_PW_ON=0 in the stock sec_nfc.h. FIRM is raised
only after normal-mode power-up, then the driver waits 100 ms before
sending commands. CLKOUT1 supplies TCXO and LDO38 retains its 1.8 V
selector. Linux NCI performs device initialization and polling.


Build the controller module with this directory's Makefile against the
exact kernel source and its NFC-enabled output configuration. Include
the full vmlinux and nfc/nci module symbol tables when building it
separately. The implementation uses the published NCI core and the
handset's pinned Samsung GPIO, supply and clock definitions. It does
not distribute vendor firmware.

[Samsung NFC active-low VEN definition](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/drivers/nfc/sec_nfc.h)

## Standard desktop service and controls

The handset now uses upstream [neard](https://github.com/linux-nfc/neard)
through its standard `org.neard` D-Bus service. Ubuntu 24.04's configured
repositories had no neard package candidate, so it was built on the phone.
Build dependencies are meson, ninja-build, libglib2.0-dev, libdbus-1-dev,
libnl-3-dev and libnl-genl-3-dev.

`build-neard.sh NEW_DIRECTORY` checks out the tested upstream revision
and builds the daemon and tag-type plugins with their upstream notices.
It runs the upstream NDEF and SNEP tests. The script never installs or
flashes. After model, BOOT, backup and operator checks, install with
`meson install -C NEW_DIRECTORY/build --no-rebuild`. With this prefix,
copy the installed `/usr/local/etc/dbus-1/system.d/org.neard.conf` to
`/etc/dbus-1/system.d/org.neard.conf` so Ubuntu loads its bus policy,
then reload D-Bus configuration and systemd.

Add a systemd neard drop-in with `Wants=g965n-bluetooth.service` and
`After=g965n-bluetooth.service` in [Unit], and
`WantedBy=multi-user.target` in [Install]. Enable the daemon.

Install settings.py at /usr/local/share/g965n-nfc/settings.py and
g965n-nfc.desktop under /usr/local/share/applications. This local GTK
frontend runs as the desktop user and provides power and scanning
controls over neard. It displays NDEF text and URI records when neard
reads a tag. It does not automatically open a URI. GNOME Settings has
no integrated NFC page in this installation, so the launcher is separate.
The initial service-only setup did not qualify a physical tag; the later
on-device trial and required corrections are recorded below.

## Qualified clock initialization and active-tag shutdown

The first physical card trial did not detect a target despite successful
CORE_INIT and RF_DISCOVER responses. The owner's stock vendor configuration
sets `FW_CFG_CLK_SPEED=0x12`. Samsung's published
[HAL clock initialization](https://github.com/LineageOS/android_hardware_samsung_nfc/blob/61bc89fa5fb6b6c3fa47f99f9aaf6cf7967fc061/halimpl/src/hal_nci.cc)
sends vendor opcode 0x28 with this one-byte value before CORE_RESET.
The controller module now implements that sequence through the Linux NCI
proprietary-command API and checks the response status. No firmware image or
RF-register blob is uploaded. The RF files and vendor firmware remain private.

After this correction the owner confirmed card recognition; neard published
one tag and four records. Three full power-down/up/read cycles each returned
one tag and four records. This verifies that specific target and NDEF path,
not all supported protocols, payment operation or secure-element use.

The active-tag trial exposed an upstream neard power-down failure: it retained
the initiator socket and NFC_CMD_DEV_DOWN returned EBUSY. The tracked
`neard-active-tag-poweroff.patch` disconnects that socket and cancels its
presence timer first. It also formats negative errno correctly. The build
recipe applies the patch to the pinned upstream source; upstream GPLv2 notices
and attribution are retained. The three NDEF/SNEP test suites pass.

An initial warm reboot also exposed a service race: a simple Bluetooth service
can be marked started before its helper has loaded NFC. neard then failed to
find the NFC generic-netlink family. Install `wait-ready.py` as a root-owned
file under `/usr/local/lib/g965n-native-nfc` and add this to neard's existing
drop-in, preserving the Unit/Install sections documented above:

```ini
[Service]
ExecStartPre=/usr/bin/python3 /usr/local/lib/g965n-native-nfc/wait-ready.py
```

The gate waits at most 30 seconds for the actual controller's bound driver
and child NFC radio. It does not change device state. Keep the installed
controller module's digest current in `pins.json`, preserve a private rollback,
and retain the existing exact-model/BOOT/backup checks during deployment.

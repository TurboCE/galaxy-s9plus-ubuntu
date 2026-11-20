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

# SM-G965N Exynos8 real-time clock

The revision 26 reference device tree places the RTC at `0x141e0000`
with separate alarm and tick interrupts. The Exynos8 Android driver
uses the S3C6410-style alarm handler without acquiring Linux clock
handles. The native patch adds this compatible and board node to the
existing Samsung RTC driver. The driver and binding retain their
upstream license notices.

- [LineageOS revision 26 device tree](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts)
- [LineageOS Samsung RTC driver](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/drivers/rtc/rtc-s3c.c)

## Rebuild the verified trial

Use the patched Exynos9810 kernel source used for the native #47 build
and an existing ARM64 output configuration. Keep the repository path
absolute for the patch:

```sh
git -C "$KERNEL_SOURCE" apply --check "$PROJECT/experiments/rtc/exynos8-rtc.patch"
git -C "$KERNEL_SOURCE" apply "$PROJECT/experiments/rtc/exynos8-rtc.patch"
"$KERNEL_SOURCE/scripts/config" --file "$KERNEL_OUT/.config" \
  --enable RTC_DRV_S3C --disable RTC_HCTOSYS --disable RTC_SYSTOHC
make -C "$KERNEL_SOURCE" O="$KERNEL_OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make -C "$KERNEL_SOURCE" O="$KERNEL_OUT" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  -j4 Image exynos/exynos9810-star2lte.dtb
```

Package the built Image and S9+ inner DTB together in uniLoader. Use
the guarded BOOT-only installer after confirming the exact model,
fresh nine-partition backup and operator consent. Refresh existing
service receipts for the new BOOT and check module compatibility
before enabling them. No build step writes the device.

## Verify on the handset

Ubuntu should expose `/dev/rtc0` and `/sys/class/rtc/rtc0/since_epoch`.
Check that the counter advances. A previously uninitialized RTC can
report an invalid date. After confirming network time synchronization,
initialize the **hardware** clock from UTC using
`sudo hwclock --systohc --utc` if the tool is installed, then repeat
the read. The trial build leaves automatic RTC-to-system and
system-to-RTC synchronization disabled.

An alarm triggered while the handset was awake and delivered an event
through `/dev/rtc0`. The clock also retained its advancing time across a separate warm reboot,
and systemd timedated exposed the same hardware time. Wake from suspend or
shutdown requires a separate hardware test.


## RTC interrupt warning correction (native #48)

The reference node left the alarm/tick flags at IRQ_TYPE_NONE. Read-only
inspection of the actual GIC distributor showed both inputs configured as
level interrupts. Explicit LEVEL_HIGH (4) preserves that hardware behavior;
the generic IRQ descriptor's earlier sysfs edge label was misleading.
The source patch now supplies LEVEL_HIGH for both SPI31 and SPI32.

For an existing qualified #48 private BOOT and its exact inner DTB:

```sh
python3 experiments/rtc/build-irq-trial.py \
  --boot "$PRIVATE_BOOT" --dtb "$PRIVATE_INNER_DTB" --output "$NEW_PRIVATE_OUTPUT"
```

The output directory must be new. This tool checks the real FDT and allows
exactly two interrupt flag bytes to change; Image, ramdisk and outer DT remain
identical. It builds only and never writes the device. Do not publish the
resulting image without separately reviewing all embedded redistribution rights.
Copy the candidate into dist/ and use scripts/g965n/install.py with a fresh
verified nine-partition recovery backup and explicit BOOT-only authorization.
An EFS mismatch is a refusal, not a reason to disable identity checks.

On the native trial, migrate guarded service receipts using the explicit
private candidate and the fresh backup manifest:

```sh
sudo python3 experiments/rtc/migrate-services.py \
  --old-root /var/lib/g965n-sensors/kernel48-nfc \
  --new-root /var/lib/g965n-sensors/kernel48-rtc-irq \
  --backup-manifest "$PRIVATE_BACKUP_MANIFEST" --boot "$PRIVATE_CANDIDATE" \
  --confirm-sm-g965n-rtc-boot-only
sudo python3 experiments/rtc/verify-awake.py
```

Migration refuses a different kernel release, unexpected receipt/config pins,
changed protected partitions or an existing destination. It keeps prior service
settings; do not rerun against a partially created destination without reviewing
its failure. The alarm check preserves an existing alarm by refusing to proceed,
uses one four-second alarm, and clears its alarm in a finally block. It does not
qualify suspend wake or cold power retention.

Hardware verification on 2026-11-20: initial boot and a separate warm reboot
retained the RTC time, advanced the counter, delivered the awake alarm and
showed no invalid-IRQ warning or kernel call trace. Audio, Bluetooth, cover and
sensor services returned after migration and after reboot. Wi-Fi HTTPS returned
204. NFC enumerated and neard started; this is startup regression evidence,
not a new physical tag-reading trial.

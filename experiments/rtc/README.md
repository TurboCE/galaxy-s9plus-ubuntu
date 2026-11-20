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

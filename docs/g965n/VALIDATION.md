# Validation matrix

Evidence date: 2026-11-18. Korean SM-G965N, Exynos9810 rev26, 256GB,
stock Android 10 G965NKSU5FVA2 before recovery installation.

| Item | Evidence | Status |
|---|---|---|
| Identity | Android/Download Mode and recovery G965N bootloader prefix | Verified |
| TWRP | ADB recovery, 3.3.1-0, root; RECOVERY readback equals official image prefix | Verified |
| Repository backup tool | device.py ran on hardware, nine byte counts and SHA256 matches | Verified |
| Repository firmware extraction | VENDOR ro,noload; three files transferred and device hashes matched | Verified |
| Docker preparation | build.sh prepare built the new Dockerfile, including regulatory data | Verified |
| Automated guards | Fourteen recovery/network/MMIO-dispatch guard tests | Passed |
| Original G965F kernel + uniLoader | Local build and header checks succeeded | Build only |
| Ubuntu ARM64 userspace | Original local recipe produced 3200MiB ext4, e2fsck clean, build exit 0 | Built |
| Source-only recipe, complete kernel/rootfs run | New complete run still pending | Not qualified end to end |
| G965N Ubuntu boot / display / USB SSH / Wi-Fi | No Ubuntu BOOT or USERDATA writes yet | Not tested |
| LTE/audio/BT/camera | Not implemented in this mainline baseline | Not working baseline |
| Suspend/deep idle | Upstream limitations remain | Not qualified |

Local baseline rootfs SHA256:
`1dc8054f7ac3da10f5d7ba78bb5f8842c9cba5aa0c4957aab89b6baa6e19d56a`.
This is a build record, not a published image or a hardware certification.
CI never flashes, publishes images or accesses proprietary firmware.

# Third-party components

| Component | Where | Origin | Licence |
|---|---|---|---|
| uniLoader | `bootloader/uniLoader/` | https://github.com/ivoszbg/uniLoader, plus this port's `configs/star2lte_defconfig` | see `bootloader/uniLoader/LICENSE` |
| Samsung UFS PHY calibration | `src/ufs/ufs-cal-9810.[ch]` | Samsung Exynos9810 vendor kernel, unchanged | GPL-2.0 |
| MAX77705 charger driver | `src/soc/max77705_charger.c` | mainline Linux v7.1 (Dzmitry Sankouski), with this port's `charge_behaviour` addition | GPL-2.0 |
| Pinned upstream copy of that driver | `src/reference/max77705_charger.c` | torvalds/linux v7.1, unmodified | GPL-2.0 |
| `exynos-bootfb.c` | generated at build time | `drivers/gpu/drm/sysfb/simpledrm.c` from the kernel tree being built, with `DRIVER_NAME` renamed | GPL-2.0 |
| BCM4361 firmware, NVRAM, CLM blob, Bluetooth patchram | omitted; user-provided local inputs | Samsung SM-G965F stock firmware | Not redistributed here; permissions not established by upstream upload |
| `regulatory.db`, `regulatory.db.p7s` | not tracked; obtained locally from Ubuntu | `wireless-regdb` | package-specific notices |
| TWRP 3.3.1-0 for star2lte | not in this repository | https://twrp.me | its own terms |
| Boot logo | `branding/shero_logo.ppm` | this project (`scripts/build/make_logo.py`) | GPL-2.0 |

The firmware blobs are device firmware, not part of the kernel's own source.
They are NOT distributed here. Users stage their own local inputs for WLAN=1 builds.

The optional experiments/audio/snd-zrn-abox.c is the explicitly GPL-2.0 audio file
from Zerone-Laboratories/ztOS, pinned in experiments/audio/SOURCE.json. Original
notices are retained. Other unlabelled GPL-3.0 project files were not copied.

The optional experiments/modem/ sources retain Samsung/Lineage GPL notices.
SOURCES.json identifies the GPL-backed vendor copies and pinned adaptations;
COPYING.vendor preserves the vendor-kernel licence context. New compatibility
and verification code is GPL-2.0-only. No radio firmware or EFS data is included.

experiments/bluetooth and experiments/sensors contain only explicitly GPL-2.0
files from the pinned ztOS reference; per-file hashes appear in SOURCES.json.
Broadcom original notices remain. Sensor firmware header arrays are excluded:
the owner extracts the patch from a private stock BOOT and supplies it locally.
Bluetooth HCD, hub firmware and closed vendor daemons are not distributed here.

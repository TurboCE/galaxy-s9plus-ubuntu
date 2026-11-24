# Vehicle agent power-on review

Updated2026-11-24. Latest actual handset test: SM-G965N, native50.

## Latest actual power-attach test — 2026-11-24

Normal shutdown was requested only after external input read offline and the
model/current BOOT/protected-backup checks passed (battery89%). The owner
confirmed the display remained off for about10s, then connected only charger
power without touching Power. Boot text appeared; Wi-Fi SSH returned with a new
boot ID and the same native#50. Exact installed-image/protected-backup checks
passed again. Display manager, SSH, charging observer/guardian, cooling and power
key services were active. No code/settings/BOOT/firmware edits were made.

With the verified installed BOOT wrapper, reaching this Linux kernel establishes
that the boot chain containing uniLoader ran; no individual instruction/entry
trace was captured. In this tested condition **USB power-attach boot already
works**. The older charging-icon-only report remains unexplained. One successful
battery-backed shutdown/reattach is not all-charger, depleted-battery, physical
battery-removal or vehicle ACC-cycle qualification. No new automatic-boot patch
was necessary for this trial.

Runtime-only MUIC higher-input and hardware-WDT trials vanished on reboot as
expected. The original500mA input/default guardian path remained, not the whole
pre-reboot trial configuration. No charging/protection setting was restored or
changed during this read-only-code/settings investigation.

## Historical boundary — 2026-11-21, native48

The owner reports that connecting USB power to the powered-off handset does
not boot Ubuntu. Power-on-after-USB is **not supported/qualified** by this
installation. A normal warm reboot and service autostart do not test it.
The screen shown during the failed cold connection and whether the kernel
starts are not yet known. Do not call it a proven bootloader or PMIC failure.

The current running device is reachable and charger online1. Read-only exact
model/BOOT/protected-backup guard passed. No shutdown, PMU/PMIC register write,
BOOT replacement, firmware or Samsung bootloader change was made in this
review. GPS stays deferred and camera/fingerprint remain excluded.

## Source review

- [uniLoader entry](../../bootloader/uniLoader/arch/aarch64/start.S) supplies its
  embedded DT/kernel to main; it does not preserve the incoming bootloader FDT.
  [main](../../bootloader/uniLoader/main/main.c) and
  [boot](../../bootloader/uniLoader/main/boot.c) have no charger-only decision
  before launching the kernel. This does not prove the shim runs on USB attach.
- [Board init](../../bootloader/uniLoader/board/samsung/board-starlte.c) sets
  display triggering; it does not implement a USB cold-power policy.
- [Production init](../../device/mainline-init-boot) already arms a recovery
  fallback in INFORM2/3 after kernel entry. The
  [board reboot-mode node](../../src/mainline-dts/exynos9810-star2lte.dts)
  handles reset targets. Neither establishes behavior after full shutdown.
- Samsung's GPL kernel
  [sec_reboot.c](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/lineage-20/drivers/staging/samsung/sec_reboot.c)
  distinguishes POWER_OFF from POWER_RESET through INFORM2 and intentionally
  selects low-power charging when shutting down with external power. This is
  source evidence for separate paths, not the measured state/root cause of
  this mainline handset. Do not replay those register writes speculatively.

A running Ubuntu service can start an agent when external power appears. It
cannot execute before this boot chain starts Ubuntu. Likewise, an Android
/system/bin/lpm replacement is not a drop-in fix for this native installation.
The absence of charging arguments in the current mainline cmdline cannot
diagnose an off-mode attempt because the shim uses its embedded DT.

## Further physical qualification

Physical observation is required before a change can be selected:

1. Confirm the display on the failed attach: charging icon, Samsung logo, shim
   console, or black screen. Do not require another shutdown just to recall it.
2. For a prepared test, preserve current model/BOOT/protected-backup receipt
   and boot ID privately; ensure sufficient battery and manual power-key access.
3. Unplug USB, shut down fully, then reconnect power without pressing Power.
   Observe screen and host USB/SSH for a bounded interval; keep identifiers and
   raw observations private. Distinguish no enumeration, charging-only, kernel
   startup failure and normal boot with missing desktop/agent.
4. If Ubuntu starts, verify a new boot ID, exact BOOT and service readiness;
   otherwise recover with the physical Power key. Repeat with the intended
   vehicle adapter after a PC-USB baseline, since supply behavior may differ.

The earlier review had not run a cold-attach test; the successful#50 test is
recorded above. No builder flashes devices. Preserve RECOVERY/EFS/CPEFS/RADIO and do not update or
relock Samsung bootloaders. If the stock early path never enters the shim, an
Ubuntu startup setting alone cannot solve it; investigate the supported early
path before considering a separate power-key controller.

## Vehicle deployment acceptance still pending

Actual ACC-on cold boot, agent autostart/restart, power-loss state saving,
minimum-battery behavior, charger adequacy under load and parked-car thermal
behavior need separate qualification. No Codex agent service was installed by
this review; an existing UI app is not an unattended vehicle agent.

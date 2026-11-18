# G965N experiments and fixes

Record symptom, evidence, action, verification and remaining limits for every change.
Do not include identifiers, raw private logs, backups, extracted firmware or passwords.

## 2026-11-18 — Source-only project and reproducible tools

Baseline SheroAbi/galaxy-s9plus-mainline-linux at bcee6014fc2e44a4c4f1c34bca0a880d4b543ec3.
Copied original source with its notices, omitted ten firmware/regulatory files and original Git history.
Original paths/hashes are in source-provenance.json; original README is retained separately.
Added Docker environment, fixed Ubuntu Base/TWRP hashes, kernel tag+commit guards,
read-only firmware extraction, verified backups and explicit-consent installation wrapper.
New Dockerfile built successfully. New backup and firmware tools ran successfully on G965N.
Seven automated guard/integrity tests passed. Full new kernel/rootfs recipe still needs qualification.
Original local ARM64 rootfs build completed: 3200MiB, e2fsck successful, exit 0.
No Ubuntu BOOT/USERDATA writes or G965N Linux first boot have occurred.

## 2026-11-18 — OEM allowed did not mean custom recovery permitted

Symptom: RECOVERY rejected with Only official released binaries are allowed.
Evidence: OEM allowed and flash.locked=0, but KG Prenormal with no Internet.
Action: booted stock Android and connected Internet Wi-Fi; KG transitioned to Checking.
Verification: TWRP subsequently booted, ADB root worked, RECOVERY prefix matched official image.
Limit: not proof about every RMM/KG restriction; no universal seven-day unlock promise.

## 2026-11-18 — Ambiguous flash logs and recovery identification

A zero exit code with hidden progress output was not enough evidence of installation.
Source review found messages routed through an active progress bar can disappear from logs.
One reported recovery screen was later corrected to stock recovery.
Fix: verify exact heading, ADB recovery state, TWRP version, root and actual RECOVERY bytes.
Document immediate recovery key combination; normal Android boot can replace custom recovery.

## 2026-11-18 — Remote dd stderr corrupted a binary export

First BOOT export was 92 bytes too long: remote exec-out included dd's byte-count report.
Fix: remote `dd if=... bs=1048576 2>/dev/null`, exact size and source-device SHA256 checks.
Verification: all nine actual partitions passed; public device.py repeated the backup successfully.
Regression test rejects appended/corrupted data. Invalid early exports must never be used.

## Next

Complete the new full build; extract/compare stock G965N BOOT device trees; review rootfs;
then perform an explicitly authorized experimental install. Record first boot, USB console/SSH,
Wi-Fi, graphics, charging, temperature and repeated reboot separately. LTE/audio are separate work.

## 2026-11-18 — Firmware publication filter

A dry-run file audit found that stock NVRAM names end with txt_r02a_b2, not txt.
Replaced extension-based ignores with deny-all firmware/* and an allowlist for Markdown.
The public source repository was created with a clean root commit and no proprietary files
in reachable history. An earlier draft was made private and archived; it is not the public source.
Added a Git-ignore regression test covering NVRAM suffixes, firmware, regulatory data and credentials.

## 2026-11-18 — Runtime Wi-Fi NVRAM line endings

Original stock NVRAM keeps its input bytes/hash; the runtime rootfs copy normalizes CRLF to LF,
matching the existing kernel embedding path and brcmfmac requirements. Regression test verifies
source preservation and transformed runtime bytes. This is not a Wi-Fi hardware success claim.

## 2026-11-18 — Structural G965N/G965F comparison before first boot

Read stock BOOT DTBH: chip 0x2652, rev26 selected by range 26–255. TWRP runtime
shows framebuffer 0xcc000000 and firmware debug reservations below loader payload
0x92000000. RAM banks and touch bus/address align with existing mainline assumptions.
Details and limitations are in HARDWARE.md; inspection script reads backups only.
Experimental Ubuntu installation and first-boot diagnostics are now explicitly
authorized by the device owner. Preserve recovery and verified EFS/CPEFS/radio backups.

## 2026-11-18 — Automatic USB host address assignment

Mac host requires administrator permission for manual IPv4 setup. Added isolated
USB-only DHCP using dnsmasq-base and a static phone address 172.16.42.2/24.
Hosts receive 172.16.42.10–20; router and DNS DHCP options are suppressed so the
host uplink remains independent. Only usb0 is served; no NAT or Wi-Fi DHCP server.
Image configuration checks dnsmasq syntax before enabling the service. Hardware
lease/SSH verification remains pending until G965N first boot.
Reference: https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html

## 2026-11-18 — Wi-Fi guard recovers variable interface names

The inherited guard hard-coded wlp1s0 and could retry while state 40 was already
connecting. It could also wait indefinitely on a wedged nmcli call. Replaced it
with dynamic Wi-Fi discovery, retries only after two disconnected/failed checks,
saved infrastructure profiles with autoconnect enabled, and bounded commands.
Disabled radio/manual-only profiles remain untouched. Three regression tests
cover interface naming, ongoing authentication/configuration and explicit choices.
All ten recovery/network checks pass; actual G965N link recovery still awaits boot.

## 2026-11-18 — ACPM diagnostic read must not change touch power

Static review found touch-rail writes incorrectly nested under the DVFS command;
a valid DVFS query fell through and could power down LDO35/LDO43. Restored a
separate tsp on/off dispatch, with invalid values rejected before any MFD write.
Added lazy MMIO initialization and aligned/ranged SRAM/mailbox checks, rejecting
the known faulting first three SRAM pages before ctypes dereference. info skips
queue inspection when a descriptor points into a blocked region. Four regressions
pass, including DVFS query issuing zero MFD writes. No diagnostic MMIO was run
on the handset; hardware verification remains pending. Fourteen tests pass.

## 2026-11-18 — Isolated LTE/audio development

Pinned LineageOS exynos9810 lineage-20 kernel at 6a9461f9460ca51d1217e5069a5d5556fcc79e63
and ztOS at 8bfb09011757f06c68a055fbfd95ea07d5e4fbe1 for comparison. G965N
recovery exposes Star-Madera/CS47L93, ABOX and umts/rmnet modem interfaces.
Added only explicitly GPL-2.0 ABOX code, with star2lte + explicit enable guard,
minimum amplifier default, capture off and modem voice-memory mapping off.
Read-only VENDOR extraction verified three own-device Calliope blobs privately.
Object compilation passed. Full module initially failed: hidden SND_PCM was
removed by olddefconfig; external modules also lacked symbol/link preparation.
Added an explicit PCM-selecting Kconfig option, modules_prepare, exact vmlinux
export table, and clean external outputs. Full .ko linking then passed without
unresolved symbols. Complete experimental packaging workflow is being rerun.
No audio module or modem experiment has been loaded on the device. LTE port
still requires compatible vendor IPC/mailbox code and native userspace control;
unlabelled GPL-3.0 compatibility headers are not copied into GPL-2.0-only modules.

## 2026-11-18 — Docker builds from managed Git worktrees

Experimental kernel, .ko and wrapped boot image built, then metadata recording
failed because .git is a host-absolute worktree pointer unavailable inside /src.
Pass the host-resolved commit explicitly into Docker rather than mounting the
parent repository or relying on host paths. Kernel source commit is still
resolved inside its own Linux build tree. No flash was attempted on failure.

## 2026-11-18 — Compile-stage Shannon modem API port

Prepared GPL-backed vendor/Lineage modem IPC and mailbox sources, with original
notices/hash inventory. Wrote Linux 7.1 compatibility adapters without copying
the unlabelled third-party GPL-3.0 header. Replaced writes to const netdev MAC
with eth_hw_addr_random, and removed obsolete revision GPIO APIs in favour of
validated DT revision. Corrected an internal/public mailbox header mix-up.
Full g965n-modem.ko linking passed without unresolved-symbol suppression.
The board overlay is deliberately empty, so hardware initialization is blocked
even if opted in. No device module load, SIM registration or LTE test occurred.
Owner can insert an active SIM later; that does not block core Ubuntu installation.

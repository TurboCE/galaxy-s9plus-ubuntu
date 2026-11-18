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

## 2026-11-18 — G965N modem hardware-node comparison

Mailbox/shared-memory nodes match the stock handset byte-for-byte apart from
local phandle declarations. The modem node differed only in revision GPIO
phandle numbers. These are invalid outside their original tree, so the candidate
overlay drops them and declares the observed revision explicitly for the adapted
get_system_rev. Verification compares remaining properties and all 23 modem
subnodes against private stock BOOT and checks revision 26. All checks pass.
The active module blob remains deliberately empty: no hardware probe yet.

## 2026-11-18 — First G965N Ubuntu hardware boot

Rootfs ae4ca7012f47a06119b92a7e12fd65f39ad5de7dd08e9cbe0ff94b89703b23ff
and baseline BOOT b95db6e62e9a534cb43212a936a8cf0f0276d43b66f43efebc150a65410ea8c9
were written with complete readback verification. RECOVERY and radio/identity
partitions were preserved. Ubuntu booted: 8 CPUs, 230GiB root, zero failed units.
Owner verified desktop/touch and connected Wi-Fi; Wi-Fi-bound HTTPS200 and NTP
passed. GPU reported Mali-G72/Panfrost direct hardware acceleration, GLES3.1.
Native Git clone/pull and pinned per-CPU C compilation passed on all 8 cores
with identical object hashes. Added required developer/ALSA packages to future images.

An intentional wired disconnect removed USB reachability. Console login found
the Wi-Fi path; privileged nmcli activation and usb-gadget restart restored the
Mac's DHCP lease and USB SSH. This was user-requested disconnect, not a proven
driver failure. Recovery procedure should preserve Wi-Fi and use console/SSH.

The owner clarified full Lineage-supported hardware parity as the acceptance
target. Bluetooth has no controller, sensors no IIO/class nodes; LTE/audio
prototypes have not been loaded. USIM was inserted for later LTE testing.
Full feature parity is not achieved; see the expanded validation matrix.

## 2026-11-18 — Filesystem failure must stop before BOOT

Review found the original writer ran e2fsck and blkid in one shell and ignored
its result, so blkid could mask a filesystem failure. Added an explicit status
marker and accept only clean/repaired (0/1); missing status and transport errors
stop installation. Three regressions cover masked inner failures and lost status.
First successful installation used the previous path and optimized directories
without reported errors. The stricter guard applies to future installations.

## 2026-11-18 — Reproducible first-boot and recovery profile

Published the observed basic success profile with local artifact hashes, explicit
remaining hardware gaps, and no credentials/blobs. Added a manual on-device
USB recovery helper matching the tested Wi-Fi/console recovery sequence.
Git/build/ALSA tools are now included in the recipe rather than a forgotten
post-install step. Added host-resolved source-commit metadata for worktree builds.
Local password policy remains configurable with an explicit short-password
opt-in; no actual device password is published or stored in the profile.

## 2026-11-18 — GPU evidence, board ports and reversible kernel tests

The baseline log contains nautilus INSTR_INVALID_ENC and GNOME/Xwayland
DATA_INVALID_FAULT jobs. A prior on-screen gears result was screen-locked and
is not a meaningful FPS benchmark. Added an independent surfaceless EGL test:
Mali-G72 rendered and read back 100 changing texture patterns (6,553,600 bytes)
with zero mismatches; the bounded kernel log plus cooldown had no new faults.
This does not resolve the earlier desktop faults.

Imported explicitly GPL-2.0 Bluetooth and BCM4773 transport files with pinned
source hashes/notices. Compared UART, expander, wake/handshake and amplifier
addresses/pins against this handset's private stock revision-26 tree. Added
model/opt-in guards, Bluetooth partial-registration cleanup and board quirks.
Removed sensor firmware arrays and replaced them with request_firmware.
Fixed transport init-error propagation/partial cleanup and patch read bounds.
Extracted the own-device hub patch from original BOOT, structurally validated
it and checked it equals the reference Android10 payload. Output remains private.
Read-only VENDOR inspection and own Calliope staging passed. A read-only EFS
check found no Wi-Fi module-vendor record at wifi/.cid.info; no EFS write.
Installed EGL development libraries and BlueZ for controlled tests.

Built the experimental kernel with ALSA, Broadcom HCI, SPI and OF overlays,
and linked all four external modules without unresolved-symbol suppression.
BOOT SHA256 ac5a362c9309ff9b84b4776f1e48ca4eb97c84836ac3087548b17fe485b5b11d,
27,084,816 bytes; kernel build #6. No driver loaded or new kernel booted yet.
Added an explicit BOOT-only installer mode that runs the existing G965N and
nine-partition backup/identity checks while preserving USERDATA and RECOVERY.
The consent regression initially failed on argparse wording; restored explicit
consent validation before any device access. All 20 guard regressions pass.

## 2026-11-18 — Experimental #6 hardware boot and desktop integration

Kept a full private copy of the working Ubuntu BOOT. The first kernel update
stopped before writing because EFS differed from the previous raw backup.
Compared copies offline: all 127 regular files identical, no additions/removals;
only superblock mount/write times/count metadata changed. Exact source of that
metadata change is not established. Took a fresh nine-partition verified backup;
did not weaken identity checks. BOOT-only write/readback passed and #6 booted
with USB SSH and zero initial failed system units. USERDATA was preserved.
systemctl reboot recovery was rejected; the supported --reboot-argument=recovery
form reached TWRP. No bootloader or RECOVERY update.

Audio manual load with cp_vss=0 booted Calliope CRL0 and registered speaker PCMs.
2s zero-data playback took 2.185s, no watchdog recovery. Reloaded with capture=1,
mic_gain=0 after stopping the user audio services; codec 0x6371 rev1 initialized.
3s capture produced 576,000 bytes, nonzero samples on both channels. A 5s
speaker/microphone test showed the expected separated 700/1300Hz peaks; owner
confirmed hearing two quiet tones. No recording is published. This is basic
path evidence, not speech/headset/call-audio quality or long-term qualification.

Owner reported no Sound input/output devices. Restored the stopped services;
generic ALSA probing exposed playback only. Added a GPL UCM profile for playback
device0 and capture device2, installed alsa-ucm-conf/pulseaudio-utils/rtkit, and
restarted WirePlumber. Phone speakers and Phone microphone appeared, GNOME
Settings connected to the real capture stream; both set as defaults, output25%.
Future images include these packages/profiles.

Bluetooth manual board load created ttySAC0; btattach loaded own-device Semco
candidate HCD and registered hci0. Discovery saw 12 distinct peers (IDs private).
Setup reported missing CMAC: CRYPTO_AES was modular but no module was deployed.
The first individual build used the obsolete aes_generic.ko target and failed;
Linux7.1 uses crypto/aes.ko. Built/loaded that exact module; cmac(aes) appeared
and controller off/on passed without another CMAC error. Future kernel recipe
forces AES built in. Pairing, A2DP and automatic restart remain unverified.

Hub transport manual load created bbd/ttyBCM/SSP endpoints. Initial standby
attempts left MCU_RESP high; not taken as a working sensor result. Added our
own restricted stock-vendor runtime: SYSTEM/VENDOR ro,noload, individual char
nodes only, no identity block devices. First lhd invocation aborted because
its default /data/etc/lhd.conf was absent. Private Android log capture exposed
the error; stock init confirms the /vendor/etc/sensor/lhd.conf argument. With
that argument, kernel reported hub ready. A deliberate 30s test-service timeout
then stopped the daemon and produced NOTREADY/CRASHED teardown notifications;
those are not evidence of a spontaneous firmware crash. No sensor samples yet.

Replaced the modem's empty embedded overlay with a bounded local DTBO request,
kept model/opt-in checks and added an exact reserved-memory layout check. The
GPL candidate still passes private stock comparison. Manual load bound mailbox,
shared-memory and modem drivers and created control/rmnet endpoints. Logs show
unimplemented vendor QoS/ECT and missing legacy reset GPIO; no CP boot/SIM/data
claim. RADIO/EFS/CPEFS are not written by this stage.

Owner reported oversized Firefox. Automatic3x left 480px logical width; applied
persistent2x via Mutter API, yielding720x1480, with auto-maximize/centering on.
The first call's optional layout-mode property was rejected; omitting it passed.
The reusable helper initially indexed the mode's scale list incorrectly; corrected
to field5 and ran it successfully. Saved a fresh-image display profile. Larger
application minima remain a limitation; no all-app fit guarantee.

Owner reported Korean squares: no Korean font was installed. Added Noto CJK and
emoji, explicit ko->KR fallback and font-cache refresh. fc-match selects Noto
Sans CJK KR; Pango's Korean sample has zero missing glyphs. Existing app caches
may need reopening. GPU acceleration remains active but additional GNOME job
faults were observed on #6, including JOB_BUS_FAULT; not marked stable.

## 2026-11-18 — SSP write contract, bounds and first motion readings

An original GPL-2.0 diagnostic client based on Lineage protocol definitions
rejected the first command's write result. The board character driver returned
the BBD transport count (user size plus2), violating write(2)'s byte contract.
Review also found a1024-byte accepted user packet could overflow the internal
1022-byte payload array. Added a bound inside bbd_send_packet and a1022-byte
character-device limit; empty writes do nothing, accepted writes return user
bytes, and queue exhaustion returns EAGAIN rather than false success.

Rebuilt the sensor module, stopped the bounded lhd test, unloaded/reloaded the
transport and restarted the own stock daemon/config. The fixed SSP client read
chip0x55, firmware21031900 and the sensor mask, then19 accel and18 gyro samples.
All axes varied during the short run; values remain raw with no claimed units
or orientation calibration. One other frame was not decoded. Sensor removal
commands were serialized and no AP sleep/wake commands were sent.
On-device zero-length write returned0;1023/1024-byte writes returned EMSGSIZE
before reaching the hub. No calibration or identity partition was written.
Raw motion readings are verified, but IIO/automatic-rotation integration and
longer power/restart tests remain open.

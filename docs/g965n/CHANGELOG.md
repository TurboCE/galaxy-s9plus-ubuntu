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

## 2026-11-18 — Protected modem boot, SIM recognition and GPU isolation

Extended the private vendor runtime with extracted backup-file NV working
directories and a read-only regular RADIO copy. No original EFS/CPEFS mount.
Verified a closed systemd device policy actually denies access to all three
physical block devices; cbd receives only its modem character-device allowlist.
The first bounded cbd run could not access private files after dropping to
Android radio UID1001. A private strace showed EACCES, not a CP driver failure.
Made the chroot root/search directories traversable inside the root-only host
parent; granted UID1001 ownership only of cloned nodes, firmware and NV files.
Adjusted the private Android log socket for that UID. Original paths untouched.

With corrected permissions, CP reached ONLINE. Opening IPC/RFS channels completed
the AP startup gate; the state probe received SIM status0 (ready),130 (initialized),
and phone-state1. AT queries also returned CPIN READY. CFUN=1 was accepted;
subsequent queries show LTE operator selection/search (CEREG0,2), packet attach0,
and CFUN query still0. This is not registration or Internet success. Owner says
the SIM was used for laptop data; subscription/device eligibility is not established.
The current state-only probes drain but do not answer RFS; a complete persistent
control/filesystem path remains necessary. No SMS/calls/PIN/identity queries.
Physical EFS/CPEFS/RADIO SHA256 values still exactly match the fresh backup.
Bounded cbd test timeouts are deliberate and must not be called spontaneous crashes.

Built a second kernel, with AES built in, from source commit eb75af0:
BOOT a87cf82f9e4bb9cede1365492b8ae8ce76e934730f5f27210b04edf57c2f2415,
27,088,912bytes. Not flashed/boot-qualified yet.

Firefox/desktop activity produced real GPU scheduler timeouts on #6. Tested
always_on=Y from23:12:14: four100-frame readback runs passed without mismatch or
fault in their bounded interval. A later GNOME DATA_INVALID_FAULT at23:19:47
disproved this as a complete repair. Restored always_on=N; no persistent policy
change. Battery sensor35.6C observed; CPU thermal limiting remained active.
Vendor and mainline both derive DMA address width from GPU MMU properties;
stock G965N DT has no coherency override. No speculative DMA/coherency edit made.

## 2026-11-19 — Private RFS replies, LTE registration and staged startup

Implemented an original GPL-2.0-only bounded RFS server using public protocol
definitions, not GPL-3.0 userspace implementation code. Reassembles fragmented
requests; only fixed private nv_data.bin working copies can be read/written.
Checks salted MD5 before use, rejects symlinks, validates ranges, fsyncs updates
and replaces the working checksum. Remote filesystem paths are refused. Actual
100286-byte and approximately20KiB NV writes received replies; a subsequent
restart accepted the resulting working checksum. Three regressions verify
copy-only writes, range/path rejection and checksum/symlink rejection.

RootDirectory with default API mounts hid the prepared runtime; disabling API
mounts with that launch failed203/EXEC. Explicit host chroot with MountAPIVFS=no
works while retaining the closed device allowlist. Early AT configuration could
time out before readiness; added bounded harmless AT readiness checks while RFS
continues running. State-changing AT commands are not blindly retried.

Owner replaced the laptop SIM with an active KT phone SIM. Packet-only service
domain still did not provide EPS registration. With combined CS/PS domain, the
bounded test received IPC access-technology0x21/domain3/registration2 and repeated
AT +CEREG:0,1 (home EPS registration). This establishes LTE registration, not PDP
activation, an address or Internet access. SIM and configuration both changed;
do not attribute the result solely to subscription eligibility. An earlier
registration status4 was described too strongly as rejection: the older public
IPC definition means emergency-only, so rejection causes remain unproven.
No SMS, calls, PIN or subscriber-identity queries were sent. RFS/cbd are bounded
tests, not persistent services. Physical protected partitions require another
post-test hash check before making a new unchanged-partition claim.

Built source-only module receipts and an opt-in startup installer. Staged audio
and Bluetooth services for BOOT a87cf82f9e4bb9cede1365492b8ae8ce76e934730f5f27210b04edf57c2f2415
with built-in AES. Each service checks the running kernel, actual BOOT prefix
and module SHA before loading. No modules loaded during staging. The handset
still runs kernel#6; #7 and startup persistence have NOT been boot-verified.

Installed glmark2-es2-wayland. Mali-G72/Panfrost GLES3.1 Mesa25.2.8 rendered three
512x512 offscreen benchmarks with readback and no new kernel fault in that
interval. This does not clear earlier GNOME job faults or scheduler timeouts.
No fixed-clock or no-AFBC setting has been installed at this checkpoint.

## 2026-11-19 — Reproduced GPU hangs under a complete scene sequence

On kernel#6, ran all33 glmark2 GLES/Wayland512x512 scenes (one-second
scene duration). The program printed a score but the bounded kernel delta
contained repeated job-slot0 scheduler timeouts. A score is not acceptance.
The earlier three short offscreen/readback scenes did not expose this failure.

Parked the lab modem with its documented CP power-off ioctl because bounded
RFS/IPC services had ended; this avoids leaving an unsupported CP session running.
Temporarily capped GPU devfreq at260MHz with its minimum already260MHz. The same
sequence still timed out. Restored max572MHz. Disabling flush reduction also
produced timeouts before a later overlapping test; that overlapping tail cannot
be used as a controlled comparison. Restored flush reduction=Y. A separate
non-overlapping PAN_MESA_DEBUG=noafbc run still timed out, so disabling AFBC
for an individual client is not a complete repair. A sync-mode run did not
complete within55seconds and still had a timeout in its kernel delta; no global
Mesa debug setting installed. Runtime-PM override remainsN and step-voltage
reduction remainsN. No new kernel was flashed.

Paused disruptive GPU workloads/reboot tests while the owner uses the handset.
GPU correctness, compositor smoothness and long-term stability remain open.

## 2026-11-19 — GPU backing failures and diagnostic kernel preparation

An interactive desktop renderer also raised DATA_INVALID_FAULT. Later a desktop
client repeatedly hit the WARN at panfrost_mmu_map's get_pages_sgt failure path;
GPU shrinker purges were frequent while MemAvailable still exceeded2GiB. This
suggests allocation pressure in the restricted DMA zone, but the exact allocation
error and its relationship to job faults are NOT yet proven. The port currently
forces every new Panfrost BO below4GiB to permit DECON imports, although Mali's
own MMU supports wider addresses. Do not confuse that policy with a Mali limit.

Enabled Panfrost dump_core temporarily for private fault capture; no dump or
framebuffer content belongs in Git. Added source diagnostics for timeout owner
and backing-allocation errno/size, preserving failure returns. Added a runtime
s9p_lowmem_bos switch for NEW allocations only, defaulting to the old policy.
No existing buffer is moved; unrestricted allocations may fail DECON import and
require rollback. These are diagnostic changes, not a claimed GPU repair.
The owner explicitly authorized continuing reboot tests after using the device.

Diagnostic kernel#8 built: BOOT0084314ebcdfbe15d57e804b20e72d254682f840b5e5dd905e62fa9c95204b17,
27,088,912bytes, UTS#8 Nov18 15:32:53UTC. The direct container call initially
could not resolve the host worktree's external .git pointer, leaving a blank
source receipt. Regenerated the receipt with the actual host a3f3c66 revision;
a mistyped intermediate receipt was corrected before deployment. Added a
fail-fast source-revision check for future direct container calls. The normal
host build wrapper already supplies the revision. Kernel/image bytes unchanged.
Staged exact#8 audio/Bluetooth guards; no module load during staging. Repeated
physical EFS/CPEFS/RADIO hashes exactly match the pre-kernel backup after RFS tests.
Requested recovery reboot; BOOT not yet written at this checkpoint.

## 2026-11-19 — Diagnostic kernel boot and allocation comparison

Fresh nine-partition recovery backup passed size/hash checks. The guarded BOOT-only
writer verified image0084314e... readback, then Ubuntu booted kernel#8. Exact-BOOT
audio/Bluetooth startup guards passed; both services active, hci0 and PCM nodes
present, PipeWire exposes Phone speakers and microphone. This proves startup
binding/policy, not another acoustic or Bluetooth peer test. #7 was never flashed.

Default#8 completed100 exact readback frames and all33 scenes, but35 matching GPU
error log lines made qualification fail. The new timeout diagnostic identifies
actual glmark jobs as well as compositor jobs. Turned s9p_lowmem_bos=N only after
that suite ended. Unrestricted new allocations still completed the suites but
produced73 error log lines, so this does NOT fix scheduler hangs. A separate
memory-pressure reproduction is still necessary for the backing-allocation issue.

Next isolated runtime suspend using the GPU device's power/control=on (not just
the G3D-domain always_on override, which still allows Panfrost internal core/L2
shutdown). A POSIX-sh readback command used unsupported brace expansion after
the write; explicit paths confirm the device policy is on. Test outcome pending.
Review also found the original readback test slept AFTER reading pixels, which
could flush dirty contents before idle. Moved idle before readback without an
intervening upload/redraw to test preservation more directly. Not yet run.

## 2026-11-19 — CRC hang isolation, reboot pass and memory-pressure failure

Keeping internal GPU power on, even combined with a fixed260MHz clock, did not
clear the33-scene hangs. Restored power/control=auto and max572MHz. Isolated the
ideas scene using sync mode: nofp16, nocache and linear still aborted with a GPU
timeout. nocrc passed; noafbc also passed that single scene. This implicates the
CRC/AFBC path but does not prove which hardware/driver mechanism is responsible.

With only PAN_MESA_DEBUG=nocrc (no sync), normal DVFS/runtime PM and the original
low-memory BO policy,100 exact frames and all33 scenes passed with zero GPU
error lines. Added nocrc to the image environment and current handset; preserved
the original environment privately. Warm reboot succeeded. Repeated the suite
while an interactive client ran: zero errors,100 exact frames,33 complete scenes,
and G3D counters increased by27 power-on/off pairs. The revised readback waits
before reading, so dirty output spans idle without another upload/draw.

A separate Firefox WebGL test compared120 frames /31,457,280bytes with zero
mismatches/context loss. Firefox exposed the privacy-normalized renderer string
'Mali-G51, or similar'; the native EGL probe reports the physical Mali-G72, and
Firefox holds renderD128. Do not describe the privacy string as another GPU.
This is bounded functional evidence, not a long desktop soak or video-codec test.

Added an optional live-texture pressure test. At768MiB nominal texture data, the
original low-RAM policy failed with CREATE_BO errno12 and the new diagnostic
confirmed BO backing err=-12, while system MemAvailable remained over2GiB.
Unrestricted allocation repeated that workload but produced a pixel mismatch
and DATA_INVALID_FAULT. Immediately restored s9p_lowmem_bos=Y. Thus merely
removing the restriction is unsafe and is NOT an installed fix. No default for
unrestricted buffers or a no-suspend/fixed-clock policy was installed.

The Lineage kernel configuration selects bv_r38p1. Its GPL device initialization
unconditionally chooses AArch64 page tables; the current generic Panfrost match
uses legacy Mali-LPAE. Hardware MMU_FEATURES=0x2830 advertises48-bit VA/40-bit PA.
This is a specific source-backed lead for the high-bank failure, not a confirmed
cause. A board-specific match using upstream's existing AARCH64 support is next.

## 2026-11-19 — Board-specific AArch64 MMU trial prepared

Confirmed the selected Lineage bv_r38p1 device/mali_kbase_device.c line312 chooses
kbase_mmu_mode_get_aarch64(). Added an Exynos9810-compatible Panfrost match ahead
of generic Bifrost, copying its existing supply/PM contract and selecting only
upstream GPU_QUIRK_FORCE_AARCH64_PGTABLE. Other GPU compatibles are unaffected.
Added a once-per-device log of the actual page-table mode. No vendor binary or
implementation was copied. This candidate has NOT yet been built/boot-tested;
keep the low-RAM policy and nocrc mitigation until hardware evidence says more.

## 2026-11-19 — AArch64 boot, high-bank pressure pass and microphone report

Kernel#9 BOOT93c36f5dbfa05ebf7a986374a31162cc77431f9bc813defe3d7e9001315c3150
(27,088,912bytes) passed a fresh nine-partition backup, guarded BOOT readback and
native boot. Kernel log confirms AARCH64_4K page tables. With lowmem=N and nocrc,
the same768MiB retained-texture workload that corrupted output on#8 now passes:
100 exact frames, all retained textures checked again, no matching kernel error.
CRC-enabled full33 scenes still fail, so the MMU fix does NOT replace nocrc.
Full33 scenes plus readback with nocrc and unrestricted allocations pass cleanly.

Prepared a safe kernel default: unrestricted BOs only for the Exynos9810 match
using AArch64 tables; legacy/other matches retain the prior low-address policy.
The diagnostic lowmem flag can force the old allocation policy. No userspace
startup write is used, so BOOT rollback cannot accidentally enable high addresses
on legacy#8. This default still needs its own boot/persistence qualification.

Owner reports a voice application cannot hear speech. Pulse input is unmuted
and the actual Chromium RecordStream is linked to the microphone. Numeric-only
capture reports low levels; no audio file saved. Changed runtime mic_gain0 to40
(+20dB, the driver's original speech default) and reopened capture. Levels rose
but owner still reports no recognition. L/R correlation near1 rules out strong
opposing-channel cancellation in that sample; this does not prove intelligible
speech. Gain change is a diagnostic trial, not an installed microphone fix.
GPU#9 tests proceeded while microphone routing was inspected. Stock IN3L/IN3R,
AIF1 registers and ABOX UAIF format/polarity match the reviewed source. Stock
media-mic additionally routes IN3L through LHPF/ASRC; direct prototype path remains
under investigation. Do not label voice recognition or full microphone support working.

## 2026-11-19 — Microphone supply bypass defect found in source/readback

Codec readback after capture showed MICBIAS1=0x8066. Its reset BYPASS bit1 remained
set: codec_start updated mask0x81e1, which changes the1.8V selector but never clears
bypass. The stock G965N DT requires a regulated1.8V MICBIAS1; the Lineage Madera
supply/bypass path clears this bit for regulated operation. Changed mask to0x81e3
and added a readback check, disabling the bias and returning EIO if it does not
latch. Child active-discharge settings remain as the stock DT specifies. This is
register-configuration evidence, not a physical voltage measurement or speech pass.

Prepared speech-default mic_gain40 in the opt-in startup package (speaker gain
unchanged). The previous gain40-only trial failed user recognition; do not call
this a gain-only solution. Kernel#10 with safe GPU allocation default was built
but never flashed; next build includes the microphone supply correction as well.

## 2026-11-19 — Kernel#11 boot, microphone recording and display-import regression

Kernel#11 BOOT b3210c87fc1a679136a2f98ad915590ed89bbd83f88099c651d45f1fb59f5ee1
(27,088,912bytes) passed fresh nine-partition backup, guarded BOOT write/readback
and native boot. RECOVERY/EFS/CPEFS/RADIO were not flashed. Actual MICBIAS1 readback
8065 clears bypass while capture runs; the configured1.8V is not a measured
physical voltage. Owner still reports no application speech recognition.

With explicit recording/playback authorization, added a bounded private-tmpfs
record/replay helper. The first10s sample had peak690/RMS56.4 and replay used9.5x
normalization; owner heard sound and white noise. Owner subsequently clarified
that they had not spoken for this test, so this is NOT speech/intelligibility
evidence. A clearly announced repeat was started. No recordings enter Git.

Tested a temporary WebRTC voice processing source. One-shot pw-cli load exited
and removed its nodes; keeping an interactive client alive produces a real source.
Initial AGC trial clipped14 samples; disabled AGC rather than promoting it as a
fix. The no-AGC stream returns samples with no clipping in a15s numeric probe;
quiet tail monoRMS3.2..3.9. Those are different ambient intervals, not a measured
SNR improvement. Default input remains the physical microphone. AEC, intelligible
speech and Lineage multi-mic parity remain unverified; no persistent filter yet.

GPU#11 AArch64/nocrc passed1024MiB retained-texture readback, but real desktop
clients exposed DECON swiotlb buffer exhaustion when high BOs were exported.
The prior acceptance regex missed these display errors. Added this signature
and a regression test. Restored runtime lowmemY and conservative source defaultY,
including repair of previously patched build trees. Installed#11 still defaultsN
after reboot; source change alone is not device persistence. Private-vs-shared
BO allocation needs a coordinated kernel/Mesa fix before unrestricted defaults
can be considered. No full GPU-normal claim is made.

Owner spoke in the announced repeat:10s, peak832/RMS95.6, normalization7.88x.
Owner recognizes their voice but reports robotic/crackling sound: speech is
captured, but quality FAILS acceptance. Stopped the temporary WebRTC filter;
it was not the default input for this recording. PipeWire logs show repeated
playback follower resyncs (hundreds suppressed) and a prior broken-pipe recovery.
A reversible handset-only WirePlumber trial now requests1024-frame periods,
1024-frame headroom and non-mmap I/O for the ABOX nodes. The same recording is
replayed to separate playback corruption from capture corruption. This is an
unqualified diagnostic setting, not the installation default or a quality fix.

The owner initially reported robotic/crackling artifacts gone on the same-file
replay, then clarified speech is much clearer but occasional crackling remains.
Record this as partial improvement, not a quality pass. The bounded replay logged
no new PipeWire errors and both nodes expose the requested properties. Added the
exact GPL-only WirePlumber0.4 trial rule and rollback instructions under the audio
experiment; no base-image default or unverified processing feature was enabled.
A cue-assisted repeat is in progress. The first cue wrapper invocation missed
its required recording flag and exited before the cue/capture; corrected arguments
and restarted the bounded test. No extra recording was produced by that failure.

The subsequent cue-assisted10s spoken test (peak455/RMS61.4, replay14.4x) was
confirmed by the owner as clear with no crackling. No new PipeWire errors were
logged in that bounded interval. This establishes short spoken recording/replay,
not long stability or all microphone functions. Included the exact ABOX-only
WirePlumber0.4 rule in the image overlay so the tested path is reproducible;
it does not enable the optional driver. Added optional quiet cue/start delay and
exclusive recording lock to the helper to avoid ambiguous instructions/overlap.
Application speech recognition is being tested separately. No app installation
or personal configuration is published.

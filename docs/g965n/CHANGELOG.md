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

## 2026-11-19 — Voice recognition confirmation and GPU#12 guarded deployment

After the timing rule, owner confirms the voice application recognizes speech
and responds. This is an actual bounded application test, not all audio/mic
functions or telephony parity. Removed only our four private runtime recording
pairs after comparison. Installed the exact source rule under its canonical name,
retaining the previous trial text privately; did not leave two active rules.

Owner reports black shapes at the top/bottom across desktop applications. A local
GNOME screenshot does not contain them; owner photo does. Owner reports they are
not visible in TWRP. This narrows investigation but does not by itself exclude
panel damage (different backgrounds/output configuration). No fresh GPU fault
lines in the inspected interval. Added a screenshot utility for diagnosis; all
screenshots/logs remain private. Initial direct screenshot API was denied; the
normal screenshot utility succeeded.

Kernel#12 built from63f8768, BOOT
2b1dffe3aab8e968f41baa428d88e66b6397e2893ab68b20ac7862d866f87dd4
(27,088,912bytes), restores conservative low BO allocation at boot. Passed a fresh
nine-partition backup and guarded BOOT-only write/readback. Exact-BOOT audio/BT
startup staged before reboot. Native boot and physical artifact check are still
pending; build/readback is not device success. No protected partition was flashed.

Kernel#12 native boot confirmed exact UTS and conservative lowmemY without a
runtime override. Exact-BOOT audio/BT services active; both UCM nodes and timing
rule persisted. Owner reports black top/bottom shapes gone. The reboot and
allocation default changed together, so the precise cause is not isolated.
Full33 GLES scenes plus100 exact readback frames pass on physical Mali with
nocrc and default PM/DVFS; new kernel fault signatures, including swiotlb, count0
in that cursor-bounded interval. Whole-boot logs still contain optional regulator,
other driver probe/P2P and initramfs warnings; a clean test interval is not a
clean whole boot. Desktop animation smoothness is explicitly not yet qualified.
Added an ignore for private chat attachments; no photo is committed.

## 2026-11-19 — Optional GPU regulator mismatch candidate

Whole-boot audit found `_opp_set_regulators: no regulator (mali) found`, even
though later DVFS/render tests ran. Source confirms Panfrost treats ENODEV here
as optional and continues. The Exynos board match had copied the generic Linux
regulator list, but this port's s9p-g3d clock provider actually programs BUCK6
through ACPM before publishing the clock, and refuses publication on failure.
Prepared board data with no Linux regulator supply and skip OPP regulator setup
only when num_supplies is zero. Frequency OPPs/devfreq and real ACPM failures
remain active; other boards with supplies keep their original validation.
This models existing rail ownership; it does not mask a failing voltage command
or prove animation performance. Candidate build/boot qualification pending.

## 2026-11-19 — Actual animation latency captured

Installed the distribution Sysprof capture development package for diagnosis.
Its library/header notices remain external; none are copied into the project.
GNOME denied automatic ShowApplications; stopped that attempt and restored the
prior overview state. Did not bypass that access restriction. Captured25s via
the normal Sysprof FD API while the owner exercised the UI.257 FrameClock marks
have p95=34.74ms/max240.52ms; paint-view p95=29.34ms, swap max157.92ms and queued
input processing max229.25ms. This confirms latency spikes but not their cause;
mark durations are not presented FPS. Raw capture stays private. Added source
capture/API analysis helpers and repeat instructions; no raw trace committed.

Kernel#13 candidate with corrected rail ownership built successfully from08e6464,
BOOT e86e3b48b3765b60c1eb5a7b85929a7e983684597253a8e8fc4784c89d5662ac.
It is not installed/boot-qualified yet; running device remains#12.

## 2026-11-19 — Kernel#13 native rail-ownership validation

Fresh nine-partition backup completed. An initial installer invocation named a
nonexistent timestamped image; preflight refused it before any write. Re-ran with
the actual manifest-matching artifact, verified BOOT-only readback and native
boot#13. BOOT e86e3b48b3765b60c1eb5a7b85929a7e983684597253a8e8fc4784c89d5662ac,
27,088,912bytes, UTS Nov18T17:14:11UTC. Protected partitions were not flashed.
The `_opp_set_regulators` missing-mali-supply error is absent from this full boot,
not just the benchmark interval. GPU initializes at572MHz/950mV in the dedicated
clock provider, AARCH64_4K and conservative lowmemY confirmed. No matched GPU/
display faults, panic/oops/WARNING/SError/lockup in the inspected whole-boot log.
Audio/BT exact-BOOT services active, hci0 and both GNOME audio nodes present;
this does not repeat the earlier owner's acoustic/ASR test after this reboot.
No failed system units in the check. The next bounded GPU/DVFS check is running.

Other boot messages remain: clkout probe-22, initial s6sy761 probe-110,
MAX77705 child DT-node messages, Wi-Fi roam/P2P failures and SO_PASSSEC unsupported.
The existing uniloader build script explicitly records why its20byte empty-gzip
external ramdisk is retained: changing it to an empty cpio historically hung
before console. Kept that known warning path unchanged rather than repeating
that unsafe workaround. It is not represented as an entirely clean boot.
Raw animation traces used runtime storage and expired on reboot; numerical
summaries above were read before reboot. Future repeat captures should use a
persistent private output path when follow-up analysis is required.

Kernel#13 full33 scenes and100 exact readback frames passed with0 matching
GPU/display errors.50ms frequency samples observed260/455/572MHz (239/14/580
samples), rail-setting readback950000uV throughout;15 more power-on/off cycles.
Both CPU policies also changed frequencies (little350..1499MHz, big1066..2327MHz)
during this bounded test. This establishes functioning observed DVFS, not a
physical rail-voltage measurement or animation smoothness. No fixed-frequency
or always-on performance workaround was installed.24 host guard tests passed.

## 2026-11-19 — FIFO pacing baseline and sequencing candidates

On native#13, three512x512 Wayland FIFO/vsync scenes (build/texture/ideas,4s each)
all measured31fps /32.4..32.9ms, despite the much higher unconstrained score.
Source audit found DECON waits for shadow latch then arms the event for the
FOLLOWING vblank. Prepared completion on the already-counted presenting edge,
only if both shadow latch and FRAME_START sequence advance are observed.
Otherwise retain the core's armed-event fallback. Vblank references are obtained
before programming the flip and transferred/released on exactly one path. Added
a runtime diagnostic old-policy switch and completion counters; no fixed clocks,
animation-disable setting, IRQ/TE timing or framebuffer reuse protection removed.
This candidate is not hardware-qualified yet.

Boot logs show touch I2C timeout BEFORE ACPM's successful touch rail reset, then
successful rebind. Prepared a board-only readiness/defer guard until the existing
reset and one-second startup delay complete. Actual post-ready I2C failures still
propagate. Rail reset limits/retry logic preserved. Added SECURITY_NETWORK support
for the SO_PASSSEC socket option requested by journald; the kernel socket source
explicitly returned EOPNOTSUPP when this configuration was absent. This does not
claim an enforcing LSM or fix by suppressing logs. All candidates await build,
guarded boot and hardware validation.

GNOME shell also logged missing Dbusmenu introspection support. Installed the
distribution gir1.2-dbusmenu-gtk3-0.4 dependency on the handset; a fresh gjs process
successfully imports Dbusmenu. Added that dependency to the existing desktop
AppIndicator package list. Existing GNOME process caches imports, so absence of
the startup error still needs the upcoming session restart. No personal app
installation, account or setting is part of this source change.

Added optional FIFO acceptance to gpu-validate.py and two guard regressions:
31fps cannot qualify even alongside a high score; missing/duplicated scene labels
cannot qualify.26 host regressions pass. Current kernel build still uses the
committed228d4bd driver inputs; later diagnostic/package-only edits do not alter
its BOOT receipt. No candidate has been published as hardware-qualified yet.

Checked installed package/kernel-hook inventory: no distribution linux-image
package or kernel-postinst hook manages this handset's BOOT. Documented ordinary
userspace updates versus explicit custom-kernel/module replacement and major
userspace format compatibility. Added no blanket package holds or automatic
flash/update hook. Current source-only recipes retain exact-BOOT module guards.

Kernel#14 built from228d4bd: BOOT
11e29751187be847f4e856e346c9e6cc570390a62950eb304586fff8f0cd8122,
27,088,912bytes, UTS Nov18T17:42:33UTC. Build succeeded; native boot remains
pending. Staged matching audio/BT startup and requested recovery for a fresh
backup and BOOT-only deployment. New diagnostic helpers are userspace-only.
The full SECURITY_NETWORK rebuild used the existing isolated build container;
its CPU quota was raised from2 to3 then4 while other containers were idle.
No unrelated container was changed. Owner prioritizes GPU over the newly
requested short-power-key screen-only mode; that feature is queued, not installed.

Kernel#14 fresh nine-partition backup and guarded BOOT-only write/readback passed;
native exact UTS and owner boot confirmation obtained. Audio/BT startup remains
active. Touch binds after one LDO cycle with no initial I2C timeout/probe-110;
its separate upstream non-MT axis warning remains under investigation. AF_UNIX
SO_PASSSEC set/get now returns1 (old#13 returned errno95); journald's missing-option
message is absent from the inspected boot. GNOME missing-Dbusmenu import messages
count0 after restart. No failed system units in this check. FIFO old/new-policy
comparison is in progress; animation repair is not claimed yet.

On the SAME#14 kernel, old-policyN FIFO build/texture/ideas measured31/31/31fps;
latch-policyY measured60/61/61fps. Both processes exited0 on physical Mali-G72.
Counters show1310 latch completions and415 deferred completions after comparison;
the latter includes the intentional old-policy interval. RestoredY in finally.
Owner reports improvement but remaining animation stutter: full smoothness is
NOT claimed. The following25s manual profiler capture contained only its256byte
header, and the numeric touch window saw no events; these are not valid frame/
physical-touch evidence. Summary correctly rejected the empty capture; a follow-up
JSON read of the empty output failed and must not be treated as a result. Need
capture/UI overlap validation and a repeat with actual frames. FullGPU+FIFO
acceptance is now running, not overlapping the manual profile.

Full#14 acceptance now passes:33 complete scenes,100 exact readback frames and
all three FIFO scenes at61fps,0 matching GPU/display errors,16 additional G3D
power cycles. Default runtime PM/DVFS/CRC mitigation and conservative low-memory
policy retained. No forced frequency or disabled animation workaround installed.
This qualifies the one-frame completion repair for these bounded tests; owner
still observes residual desktop stutter. MemAvailable~4.6GiB and boot-to-check
pgscan_direct/allocstall/compact_stall counters0 do not support current direct
reclaim as the explanation in that sampled interval. The separate high-memory
allocation/export limitation remains an open pressure issue.

A controlled four-window GTK transition trace (normal application launch, no
restricted Shell API) contains621208bytes/126 FrameClock marks. Dispatch p95=
31.102ms/max112.062ms, paint p95=7.117ms/max81.563ms, swap p95=4.426ms/max6.15ms.
This differs from the earlier manual overview workload and is NOT an equal-workload
before/after percentage. It proves profiling works when UI activity overlaps.
Raw trace persists privately; animations remain enabled and display power mode0.

Prepared a second DECON candidate: use counted FRAME_START as a wakeup hint,
then still verify the real shadow latch under the original total50ms deadline.
The old250us polling policy is available by runtime switch. IRQ wait timeout/read
counters allow an actual old/new overhead comparison. Missing IRQs retain the
hardware-poll fallback; no event is completed based on IRQ alone. Candidate not
yet built/boot-qualified. Also included the ACPM driver's own prototype header,
and corrected the touch diagnostic to check its actual MT axes rather than
unused legacy ABS_X/Y. Real unset-MT-axis warnings remain active.

## 2026-11-19 — Kernel#15 measured wakeup reduction and independent validation

Kernel#15 (sourceccd8994), BOOT
410c776ed2cdaaf37bb798bf2138a7af35e58c5a1c029f952adbfcaf74db7c12,
27,088,912bytes, passed fresh nine-partition backup, guarded BOOT-only readback
and native boot. Exact audio/BT startup retained; touch MT-axis diagnostic now
checks real axes and no false legacy-axis warning appears in this boot.

Same-kernel IRQ-wait N/Y/N comparisons, three4s FIFO scenes each: N reads43559,
Y reads1463, N reads43473. Scene rates59..61fps throughout; Y has732 waits,
0 IRQ timeouts and0 deferred events in the interval. Whole-system context-switch
deltas129774/46039/129835 are contextual evidence under those workloads, not a
battery-saving percentage. Final Y policy restored. Peer code review identified
a possible stale-count timestamp race around request programming; a generation-
associated completion candidate is being prepared separately, not assumed fixed.

A private root-run comparison created the shared validation lock root-owned.
The next desktop-user validation correctly refused it; checked its regular-file,
no-symlink/unlocked state and restored desktop ownership/mode0600. No GPU test
ran in that failed invocation. Future privileged comparisons must create the
lock as the desktop user, rather than weaken the shared lock checks.

Two full attempts passed readback/all33 immediate scenes with0 matching kernel
faults but FIFO timed out. The first found display power mode3; the next kept
power on but the screen shield remained active. Such hidden surfaces receive no
FIFO callbacks. Added temporary GNOME idle inhibition plus power/overview/lock
preflight and end-state checks; no persistent idle preference change. Actual
inhibitor readback false→true→false passed. Standard administrative session unlock
was requested and asynchronous completion confirmed false/LockedHint=no before
the next test; no unsafe Shell evaluation or access-control workaround used.

Independent read-only audio/BT validation confirms exact BOOT/module hashes, active services,
actual SPA1024/1024/non-mmap settings, correct unmuted mic and powered hci0 with
profiles registered. Read Transmit Power warning is the existing board quirk's
intentional diagnostic, not a new command failure; it was not removed. New peer
pairing/A2DP/SCO and post-reboot acoustic quality remain untested.

Network agent confirms USB SSH, DNS and Wi-Fi-bound HTTPS200. A prior optional
accessibility package fetch failed transient DNS; no DNS setting was changed
because it no longer reproduced. Retried at-spi2-core install and actual a11y bus
address retrieval succeeded. Added it and already-installed libspa-0.2-bluetooth
to the public dependency list; no personal app installation/configuration added.
Current LTE transport is not loaded after reboot; historical KT registration
must not be represented as current LTE data service.

Power audit found real charger source defects: ICL inverse encoding,6bit CC
ceiling, CHG enable field versus CNFG09 setup bit, STATUS enum mix-up, ignored
reads and AICL minimum underflow. Prepared candidates and7 production-C/faultable-
regmap tests; hardware control tests still pending. No current limit was raised.
A60s low-load trace had positive battery current150..208mA (mean185mA), unlike
prior heavy-GPU negative current; display state was not captured alongside it,
so this is not labelled screen-off standby or an Android battery comparison.

## 2026-11-19 — Light hub protocol verified, optical response still pending

Exact#15 BOOT/module and own firmware validated before one sensor-transport load.
Only SYSTEM/VENDOR ro,noload runtime and bounded isolated lhd were used; original
identity/radio partitions were not exposed, gpsd not started. Stock argv is
/vendor/bin/hw/lhd /vendor/etc/sensor/lhd.conf. Hub ready1,chip0x55,firmware21031900,
LIGHT_SENSOR9 advertised. One5s sample and later60s stream each contain1 actual
light sample, lux/RGBW0,CCT1452,integration17,gain64,0 parsing errors. Repeated
stream lines are cached last values, not60 fresh samples. Physical cover/illumination was not confirmed, so optical response is UNVERIFIED,
not failed or normal. Bounded daemon stops/ready0 are intentional teardown.

Probe now has board/chip/layout guards, atomic bounded record parsing, unsupported/
zero-sample nonzero exit and all-sensor/SIGTERM cleanup.13 targeted regressions
pass. Prepared default-off --ap-awake asynchronous D1/D3 experiment matching
pinned SSP protocol; NOT yet sent on hardware. No coefficient/calibration/EFS
write is included. IIO/automatic brightness are separate unimplemented layers.
Further physical optical/peer tests remain unverified; code/device checks continue separately.

With the visible/unlocked desktop preconditions met, kernel#15 full acceptance
passes33 scenes,100 exact frames and FIFO61/61/61fps,0 matching kernel faults,
0 IRQ-wait timeouts and15 runtime power cycles. Display/unlocked checks remain
true at completion. The temporary inhibitor is released; actual IsInhibited
readback false→true→false was verified independently. This resolves the test-
harness false-negative cause, not every desktop performance issue.

Peer review prepared generation-associated DECON completion rather than raw
vblank-count comparison. A short bounded100us IRQ-only check accommodates latch
clear lag; ACK ordering/pending recheck and an MMIO readback avoid stale status
recount. Driver-private locks never overlap core DRM event locks. Separate IRQ-
side read counters expose that bounded work; process polling counts do not hide
it. Candidate still requires compile/boot/FIFO validation before publication.

## 2026-11-19 — Charger and generation-completion candidates for kernel#16

Charger candidate keeps original notices/reference intact and accepts cache
migration only from the exact known previous port-source hash. CHGIN encodes
current/25mA-1 (500000 requested previously read525000); CC uses its distinct
6bit3150mA ceiling rather than input7bit3200mA ceiling. Charge enable uses
CNFG00bit0 as in pinned Lineage charger state control; legacy CNFG09bit7 setup
is preserved independently, not toggled as charging inhibition. Correct STATUS
enum and read-error propagation, low-voltage health initialization and AICL
minimum underflow handling are included.7 tests execute actual production C
functions with injected regmap failures and boundary values. No live current
increase or charge-control write has been used to qualify these candidates.

The same build will include generation-associated DECON IRQ completion and
separate IRQ-read accounting. Both changes await the exact next kernel compile,
fresh backup/guarded BOOT deployment and bounded hardware tests. Existing tested
#15 remains a rollback image. No original identity/radio/recovery writes planned.


## 2026-11-19 — Kernel#16 hardware acceptance: completion generations and charging

Built source ccd336120685edfd5dddde071d0cb4c69a5cc90b, verified a fresh
nine-partition backup, then guarded BOOT-only write/readback and native boot
passed. Kernel#16 BOOT SHA256 is
06db513aac38376cda20f551523ff2af9046e9be428832581e00f34b5bbee259.
RECOVERY/EFS/CPEFS/RADIO were preserved. Exact-BOOT audio/BT startup receipts
match; this is startup evidence, not a new acoustic or peer test.

With the desktop visible/unlocked, actual Mali rendering passed100 exact frames,
all33 scenes and FIFO build/texture/ideas61/61/61fps. No matching kernel faults.
DECON deltas:2795 generation marks,2795 IRQ shadow reads,5590 process shadow
reads,2795 latched events/IRQ waits;0 new deferred events,0 IRQ-wait timeouts
and0 atomic latch-check timeouts. Runtime PM remained auto50ms, DVFS stayed
simple_ondemand260..572MHz,16 power cycles observed. Generation-associated
completion therefore passes this bounded cadence test; desktop stutter, nocrc
requirement and low-memory BO limitations remain unresolved.

Charging now reads the requested500000uA input limit rather than525000uA.
A bounded inhibit test reported Not charging/N/A for three samples with battery
current937,0,3125uA; finally restoring auto reported Charging/Fast and171250uA.
The first test expected the text None and failed its assertion: the kernel
correctly renders CHARGE_TYPE_NONE as N/A. Auto was restored in its finally
block and the corrected test passed. Fast denotes charging phase, not negotiated
USB fast charging. No current limit was increased. Original charge-control
register defect is fixed and hardware inhibition/restoration verified; full
charging negotiation, idle drain and long thermal behavior remain unqualified.

Owner is unavailable for further physical tests. Light illumination response,
new acoustic tests and peer Bluetooth tests remain unverified; no user action
is assumed.


## 2026-11-19 — Post-test idle vblank timeout; next candidate not qualified

After the successful bounded#16 GPU test, a separate idle-period kernel warning
reported drm_atomic_helper_wait_for_vblanks timing out at04:01:55KST. The
screen-button agent had not yet changed DPMS, so that test is not its cause.
The earlier test's zero-fault result applies only to its recorded interval.
No failed system units were present when inspected. Other boot warnings remain,
including CPU feature variation, clkout/MFD matching and Wi-Fi P2P creation.

Source review finds the default atomic tail waits for another vblank after
pipe_update has already delivered its latch-associated event. A command-mode
idle transfer may not provide another FRAME_START. Prepared a standard helper
tail using tracked flip_done completion instead, preserving modeset/plane/hw_done/
cleanup order and old-buffer lifetime. Existing atomic_commit initializes
internal events even when userspace supplies none. This hypothesis/candidate
requires review, compile, boot, idle-transition and full rendering validation;
it is not yet a hardware fix and no warning is suppressed.

The first candidate compile failed before image packaging because dereferencing
drm_atomic_state needs its defining drm_atomic.h header. Added the explicit
include and retried; no device write took place for that failed build.

Retry compiled and packaged kernel#17 (source ce61485aff680948b58d057e7160dbf563596e9c,
UTS Nov18 19:14:34UTC, BOOT
c159ad82b03af430c6c1afe28f7f9de95c3a7e2a9cd31010e2c58e6163bed479).
Matching opt-in modules were packaged privately. Build success alone does not
qualify the new tail; no installation or idle-timeout fix is claimed here.


## 2026-11-19 — Screen-only power handler: software path tested on#16

Added a model-guarded non-root GPIO short-release handler, user service and
active-seat uaccess rule. Raw input access is narrowed to the named touchscreen
and this model's GPIO keys. No event grab, input-group membership, suspend,
poweroff or session unlock is used. Complete short releases are debounced;
repeats, long/orphan presses and SYN_DROPPED do not trigger a display toggle.
GNOME short-button action is nothing; existing lock and long-press policies
remain independent. python3-gi is an explicit image dependency.10 host checks
pass. Source installation enables the user service for the graphical session.

After exact#16 BOOT checks and private config backups, live service ran as
UID1000 with only the intended GPIO fd, active-seat ACL and direct user-open
verified. Direct normal-API off/on took279.19/210.70ms. During8s display-off,
a separate SSH connection confirmed PowerSaveMode3 and KMS CRTC active0;
a background heartbeat continued16 times, maximum501.51ms gap for a500ms
period. No new matching GPU faults or vblank timeout in that test interval.
Original display-off/locked state was restored in finally, with no unlock
request. This verifies the software screen-only/background path, not actual
physical short/long button behavior or Android-equivalent standby drain. The
interaction between a physical key wake and release-driven toggle is pending
owner testing. Service health alone is not physical-button acceptance.


## 2026-11-19 — Private modem migration and pre-CP guards (source checks)

Added same-handset backup provenance, content-preserving legacy clone archive,
explicit fresh staging and reboot resume. Extraction uses verified root-private
snapshots rather than mutable user paths. Opaque receipts and clone content/
metadata are checked after archive; original EFS/CPEFS/RADIO are never mounted
or written. Independent review found and corrected snapshot TOCTOU and receipt
preservation issues before device use. Symlink/hardlink/special-file and bounded
NV/checksum guards fail closed. Shared client-lifetime leases prevent exclusive
runtime migration while new RIL/CBD clients hold the runtime; old clients must
be stopped. Pre-CP launchers check provenance and actual private bindings,
including read-only ordinary RADIO, before modem-off or vendor execution.

Host checks passed22 runtime,3 preflight and4 reference PDP tests. Original
reference protocol encoders/parsers describe127/103/27/4-byte legacy layouts;
these do not qualify S9's proposed105/257-byte messages. Live activation stays
blocked instead of guessing offsets. Registration or candidate IP is not data
connectivity. Migration/resume remains hardware-unqualified at this checkpoint.
Full instructions and partial-failure limits are in PRIVATE-MODEM-RUNTIME.md.


Peer review identified an existing initial/re-enable event accuracy problem:
the default planes phase invokes update before enable, so the old path could
complete an event before programming the first frame. Kernel#17 was therefore
not flashed. The next candidate retains that active-but-disabled event without
taking a vblank reference, then enable starts IRQ accounting and reuses the
normal generation/latch update path. Inactive disable commits retain immediate
event completion. This protects the completion-tail contract across initial
enable, re-enable and modesets; hardware validation is still pending.


Independent review then found a service enqueue/lease handoff race in the new
modem tooling. Added child-side validation after obtaining the lifetime lease:
parent fixes the exact verified receipt SHA, child rechecks receipt/model/NV/
RADIO/private binding before IPC or vendor exec. No additional original block
access is granted to the closed test units. CBD uses a separate flock monitor
so vendor descriptor cleanup cannot silently release the lease.24 runtime,
4 launcher and4 reference PDP checks pass; reviewer found no further immediate
blocker. Actual CBD foreground/cgroup lifetime and hardware migration still
need device checks. Nothing here qualifies LTE internet connectivity.


## 2026-11-19 — Kernel#18 installed; completion validation in progress

The reviewed initial-enable/commit-tail source88af955f61a79a670bdba6929beb23449bfeaab9
built as#18 Nov18 19:22:18UTC. Fresh complete nine-partition backup verified,
guarded BOOT-only write/readback passed and native SSH returned. BOOT SHA256
41eee11031e8287090661658445b0c72e12a3a274cb022e4c0c2ab92dec6c0f8,27088912bytes.
Protected partitions were preserved. Audio/BT services are active and exact
BOOT/module manifest checks pass. One manual check first supplied the nonexistent
audio.json filename; it stopped before verifying/loading anything. Retried using
the actual shared manifest.json and both feature checks passed.

The software regression suite now passes88 tests. New benchmark size choices
allow bounded512x512,720x1480 and1440x2960 requested surfaces; previous61fps
results were512x512 and must not be presented as native full-screen performance.
Kernel#18 rendering/idle/DPMS qualification is still in progress at this entry.

The first post-boot readback compile mistakenly requested the uninstalled and
unneeded wayland-client pkg-config package. Compilation stopped before the GPU
test ran. This diagnostic uses surfaceless EGL/GLES only; compiling against
egl/glesv2 succeeded and the hardware suite was restarted. No package install
or driver workaround was needed for that harness invocation error.


Kernel#18 bounded acceptance passed100 exact frames, all33 scenes and
FIFO61/61/61fps at requested512x512, with0 matching kernel faults and awake/
unlocked completion. Runtime PM auto50ms, DVFS260..572MHz unchanged;15 power
cycles. IRQ check-timeout counter was1 before this suite and remained1, so this
is not a claim of zero since boot. During the suite generation/latched marks
increased2795, process shadow reads5590 and IRQ shadow reads2795; no new deferred
events or IRQ wait timeouts. Idle and DPMS qualification is a separate test.


Kernel#18 screen transition qualification:3 cycles off229.34/254.32/270.16ms,
on180.43/160.52/172.90ms; off idle8/2.5/2.5s and on idle2.5s each all read
back as requested. First8s off retained16 heartbeat ticks; overall49 ticks,
maximum504.01ms gap at500ms period. A fourth cycle off237.50/on163.08ms kept
the display off12s and a fresh separate SSH connection read Mutter mode3.
KMS debugfs state was unavailable in this extra observation, not asserted.
No new vblank-wait, flip_done, latch/shadow, Panfrost fault/timeout or SWIOTLB
error since the recorded cursor. Screen-button service active with0 restarts,
original mode0/unlocked state restored in finally. Physical key behavior and
long-term idle remain unverified; bounded DPMS/idle no longer reproduces the
previous warning.

Private modem migration attempts stopped before archive/stage: first legacy
STATE root0755 failed new private0700 requirements; verified nofollow directory
FD then tightened only STATE to0700, preserving DATA and contents. Retry prepared
read-only runtime but rejected an existing EFS symlink under strict NV guards.
No clone rename/deletion/freshstage/CP start occurred. Read-only diagnosis found
the same debug-only cpdebug/node symlink in the verified original EFS backup,
so blind retry would also fail fresh stage. A preservation-only archive plus
explicit complete-source quarantine/ordinary working-copy transform is being
prepared; arbitrary links remain prohibited in working NV. Private failure
logs, uploads and inputs are retained. No LTE data success is claimed.


## 2026-11-19 — Native-resolution stress exposes remaining GPU timeout

At reported1440x2960 windowed, readback/all33 scenes and FIFO61/61/61fps
completed, but3 actual glmark JS0 scheduler timeouts produced6 matching kernel
fault lines. Overall acceptance FAILED despite the frame rate. nocrc, lowmemY
and default flush reduction were retained. CPU thermal traces briefly reached
86C and reduced allowed CPU frequency; that correlation does not establish the
GPU timeout cause. Core-dump BO-no-sgt diagnostic was also present. A bounded
flush-reduction comparison is planned without increasing voltage/clocks/job
timeouts or suppressing diagnostics. GPU is not fully stable.

The acceptance fault filter now includes vblank-wait and flip_done timeouts
as well as GPU/scanout failures; tests cover the actual warning strings.
Requested and benchmark-reported sizes are recorded separately.

Independent reviews and37 host checks passed the legacy preservation update:
opaque nofollow archive inventories preserve corrupt legacy bytes and
symlink/special metadata without opening targets. Verified source extraction
is fully retained in private quarantine. Only the exact stock EFS cpdebug/node
diagnostic symlink is excluded when constructing an ordinary working clone;
its target hash and source provenance remain in private receipts. Unreviewed
links/specials still stop staging before clone creation. Fresh-stage live retry
is authorized separately; no success is assumed from host tests.


Native-resolution flush comparison: disabling only job-slot flush reduction
(nocrc/lowmemY retained) still completed100/full33/FIFO61x3 but FAILED with4 GPU
timeouts/8 matching lines, including one GNOME compositor JS1 job. OriginalY
was restored in finally. Same-scene UTC/monotonic output and thermal samples
are retained privately; line-completion timing does not uniquely identify the
causal scene. Initial big59/GPU49C, sampled peaks78/71C, kernel big81C between
samples. This rejects flush reduction alone as the repair; no permanent disable
or clock/voltage/scheduler-timeout increase was introduced. A bounded runtime-PM
comparison is separate and still pending.

Private migration retry now succeeded on#18: source EFS/CPEFS/RADIO hashes
match the fresh verified backup; legacy opaque archive and complete extraction
quarantine inventories match; exactly cpdebug/node is absent from working NV
and retained as a symlink in both preservation copies. Salted NV checksum,
private bind identities and read-only SYSTEM/VENDOR/RADIO checks passed.
STATE0700/DATA0755 retained. No CP/CBD/RIL/PDP started. Reboot resume and actual
modem service lifetime remain separate unverified steps.


Targeted native-resolution reproduction uses interleaved buffer-map, function
low and first loop scenes8s each, followed by5s observation. Runtime PM auto
and on each produced5 JS0 scheduler timeouts/10 matching lines. In on mode
parent power counters remained78/78 throughout, demonstrating that the runtime
reference actually prevented power cycling; always_on stayedN. Thus domain
off/on alone is insufficient to explain the issue. Original auto restored.

One further bounded comparison retained PM-on and fixed only the devfreq floor
to the existing stock maximum572MHz, without voltage/timeout increases. All59
samples read572000kHz/950000uV, parent counters80/80, GPU thermal peak71C with
no observed cap, yet6 JS0 timeouts/12 lines occurred. This rules out DVFS
transitions as a necessary condition in that run. Original min260/max572MHz,
simple_ondemand and PMauto restored in finally. No new DECON errors in either
comparison. Further arbitrary configuration stress was stopped in favor of
BO synchronization/IRQ/scheduler source diagnosis. These are negative controls,
not repairs, and do not qualify GPU stability or Android battery parity.


## 2026-11-19 — Timeout register diagnostics candidate and sensor failure

Prepared timeout-only Panfrost snapshot after the existing synchronize_irq/
fence recheck. It takes a reference only if already active/in-use, snapshots
queue/fence state and job/MMU/GPU interrupt registers under the existing short
job lock, then prints outside that lock. No interrupt acknowledgement, recovery
policy, frequency/voltage or scheduler deadline changes. Sequential MMIO reads
are explicitly not an atomic hardware snapshot. Exact-anchor application and
idempotence checks pass against pinned Linux7.1; compile/boot still pending.

One bounded#18 sensor window verified exact BOOT/module/own firmware, loaded
the hub transport once and refreshed only reviewed character nodes into the
existing runtime under its exclusive lease. Shared-lease isolated lhd started,
hub ready briefly read1, but the first chip query received no valid response
within2s. Baseline exited1 with0 samples; AP-awake was never transmitted. lhd
was stopped immediately, no process remained and ready returned0. This does
not qualify sensor operation or optical response; no calibration/identity
writes or automatic restarts were performed.


## 2026-11-19 — Source-qualified S9 PDP candidate, not yet activated

Read-only static analysis of the owner's stock RIL established S9-specific
wire facts independently: definition127, activation105, IP157/base or257/
extended, status9 bytes. Original encoders/parsers now implement those fields
with strict truncation/CID/flag/address/mask/MTU checks. No vendor binary,
disassembly implementation or handset identifiers are redistributed. Raw end
reason and throttle fields are retained without guessing 3GPP mappings/units.
Peer review matched offsets to the private evidence.51 relevant host checks
and both CLI help entrypoints pass.

Activation defaults off, requires two explicit S9 opt-ins and recent complete
registration, CID1/no-auth IPv4, ordered acknowledgements and a bounded single
activation. CP reset/registration loss fail closed; no CFUN recovery loop in
this opt-in path. Best-effort deactivation is attempted at most once. Candidate
IP requires ACK+active status+valid IPv4 and is emitted once to private journal
without raw payload, credentials or device identifiers. It is explicitly not
verified internet access; no route/DNS/address modification is included.
Fixed an existing CEREG prefix regex that could misread status10 as1.
No CP/CBD/RIL/PDP execution has yet qualified this source candidate.

Timeout-snapshot kernel#19 compiled and packaged successfully; installation
and actual diagnostic reproduction still require guarded device validation.


## 2026-11-19 — Kernel#19 observations and read-only EFS comparison

Fresh nine-partition backup verified, guarded BOOT-only write/readback and
native#19 boot passed; exact audio/BT manifest matches. Source4e0740872ddd790e233fd3dc74a195b78dc86f73,
BOOT c5a3bf384f1ff0cb887199bde8aa4414fd0b2f8c7747c6829220d381831d31f8,27088912bytes.
A default-state targeted3-scene run reproduces6 JS0 timeouts and one Soft-stop
failed warning. Snapshots show the expected unsignaled queue head and pending
next job; job/MMU raw interrupt status0 with enabled masks, no GPU error IRQ.
This gives no evidence of an outstanding unhandled DONE/MMU interrupt at that
instant, but cannot exclude every IRQ race. No new display-latch failures.
This is diagnostic evidence, not a stability fix.

A separately bounded nocrc,noafbc targeted comparison also produced6 glmark
JS0 timeouts and Soft-stop failed, with no compositor timeout in that interval.
Thus AFBC compression alone is not a repair. No global noafbc setting was
installed; all clocks/voltage/runtime-PM settings and desktop state retained.
The helper accepts that exact combined debug option for reproducible diagnosis.

Fresh recovery backup revealed EFS full-hash drift versus#18. Read-only image
comparison found exactly8 changed bytes, all within primary ext4 superblock
mount time, write time, mount count and lifetime-write fields. All bytes outside
those fields are identical;127 file contents, links and on-disk inode data are
unchanged. Current recovery mount list contained DATA/CACHE only. These images
do not prove which component mounted it or when. Existing provenance correctly
refuses automatic resume; explicit verified-superblock maintenance is being
prepared, without relabelling a changed image as identical or replacing NV.

## 2026-11-19 — Sensor readiness candidate and private PDP status diagnostics

Transport ready is only lhd's ESW:READY callback; reference SSP initializes MCU
separately after waiting for init completion/delay and bounded retries. The
#18 CRASHED control message followed deliberate daemon stop, so is not evidence
of spontaneous firmware crash. Probe now pumps read-only data for5s and retries
only an exact missing chip-identity reply, at most3 attempts with1s gaps on the
same increasing sequence. Wrong identity, lost ready, malformed response or
short writes fail immediately. Sensor/AP-state commands are never retried;
chip55 plus firmware/mask must reply first.21 host checks pass; new live
readiness qualification is pending.

S9 PDP private status reports now retain selected raw state/reason/throttle
fields for rejection diagnosis, without payload, credentials or identifiers.
S9 plan tests14 pass. Units and 3GPP cause meanings are not guessed.


## 2026-11-19 — Explicit superblock provenance maintenance candidate

Added an opt-in revalidate-efs-superblock action requiring the exact old EFS
image/old private receipt and complete fresh backup/current-original checks.
CPEFS/RADIO must be unchanged. EFS comparison masks only four primary ext4
superblock maintenance fields; any other changed byte, wrong magic, backwards/
out-of-bound counters or times stops the action. Old receipt is preserved
byte-for-byte before atomic new publication with proof/history; original
partitions, working NV, RADIO, archives and quarantine are verified unchanged.
35 runtime checks and independent review pass. Host proof on the actual images
finds8 changed bytes: mount/write deltas1602s, mount count+1 and lifetime+4KiB.
Actual receipt maintenance/resume has not yet run at this entry.

With the bounded readiness delay on#19, baseline and AP-awake probe invocations
both completed with chip55/fw21031900 and0 unparsed records; motion values
varied and cleanup/daemon stop succeeded. Their aggregate sample counts include
startup settling, so cannot qualify sampling-window rates or AP-state improvement.
Both light observations remained lux/RGBW0,CCT1452,time17,gain64. Optical
response is still unverified. Phase-separated counting is being corrected.


## 2026-11-19 — Independent recovery-state correction candidate

Adapted only Arun Iyengar's upstream mailing-list proposal v3 patch12/14
(2026-11-13, Message-ID recorded beside the patch), preserving attribution/GPL
terms. It polls live JS_STATUS for all slots rather than the IRQ-clear snapshot
JOB_INT_JS_STATE before draining reset queues, and safely returns NULL on an
unexpected empty dequeue. The initiating scheduler500ms and soft-stop10ms
budgets/reset policy remain unchanged; no long-job grace-period policy from
patch13 is included. Our#19 observation of snapshot0 with live ACTIVE8 supports
this recovery-state discrepancy, not a claim to explain the first GPU hang.
Exact pinned-source/idempotence checks pass; compile and hardware recovery
qualification are still pending. Original proposal:
https://lists.openwall.net/linux-kernel/2026/11/13/872


Explicit#19 EFS maintenance and existing-copy resume now pass on hardware.
One private history entry records the8-byte proof; exact old receipt preserved
mode0600. Working NV hashes remain identical to#18 staging, archive/quarantine
inventories unchanged, original hashes match fresh#19, private binds and
read-only SYSTEM/VENDOR/RADIO validated. No daemon was started for these checks.
This verifies the explicit maintenance path, not silent acceptance of arbitrary
EFS changes.

Sensor reports now separate pre-enable counts, each sensor's enable phase and
the actual timed receive window. Each sensor array is cleared immediately
before its own A1 and all arrays again at window start. On-change initial
readings may qualify post-enable observation separately, while startup-only
data cannot qualify sampling.25 host checks pass. Previous#19 aggregate counts
remain raw startup-inclusive observations, not corrected window measurements.
No additional state command or physical-response claim was introduced.


## 2026-11-19 — Cold modem boot panicked before PDP; recovery evidence preserved

One explicitly gated#19 trial passed model/BOOT/module/source/provenance/NV/bind
preflight, then lost USB SSH. Independent targeted ADB found automatic TWRP
recovery. Preserved pstore, last-kmsg, journal and complete private modem state
to owner-private host storage before further boot. No new BOOT image was written.
Offline copied NV salted checksum remains valid. No recovery/identity/radio
flash or data replacement occurred.

Evidence contains no IPC, AT, RFS or PDP commands from the lab: the failure is
before activation. Kernel trace identifies cbd's IOCTL_SECURITY_REQUEST secure
monitor call followed by asynchronous SError/panic. Earlier MODEM_OFF central
sequence wait and CP-init interrupt-pending wait timed out, but legacy callers
ignored errors, marked initialization done and continued security requests.
The first secure response was CP_NOT_WORKING; a later request panicked. Exact
module offset maps to the security callback. This does not demonstrate an
incorrect105-byte PDP layout because no PDP request ran.

No retry, security bypass or forced PMU wait relaxation was attempted. A
fail-closed error-propagation/readiness candidate is under source review; cold
bring-up remains unresolved. Vendor mode2 positive statuses and clock-order
semantics must be audited rather than assuming every status is fatal. Returned
the unchanged#19 Ubuntu BOOT to its baseline after preserving evidence; native
SSH returned, modem is not autoloaded and transient experiment units do not
persist through reboot. CP physical readiness is not asserted from that boot.
Kernel#20 compiled but was never installed; pending work remains explicitly
unqualified.


## 2026-11-19 — CP failure containment candidate (not cold-boot repair)

Source now propagates failed PMU init/reset/off instead of continuing security
SMCs or falsely caching initialization. Checked process power transitions and
security share a mutex; IRQ handlers only advance a nonblocking failure epoch.
Only a verified explicit reset can reopen a failed session. Graceful shutdown
marks its expected offline completion before waiting; fatal/watchdog events
still invalidate the transition, including a final epoch-publication race.

SSS clock ordering required by the original secure CTRL path is preserved with
symmetric cleanup; internal positive clock errors become negative errno. The
owner CBD's independently verified mode2 nonnegative vendor-status ABI remains
unchanged. Optional pre-init RAM logging defers with EAGAIN without cold-starting
or poisoning a clean session; its former direct security path uses the same
gate. Negative secure CTRL-write errors are no longer treated as success.
Firmware authentication, SMC arguments, PMU wait sequences/budgets and protected
partitions are not bypassed or modified.

21 fault/concurrency scenarios compile and execute actual production C,
including real pthread exclusion of security during OFF, normal/fatal shutdown
completion, PMU failures issuing0 security calls, clock cleanup/status ABI and
IRQ publication boundaries. Independent review passed;19 earlier scenarios
also ran in the Linux builder. This is host/source containment evidence, not
hardware qualification. Fresh-module seq5 alone cannot reconstruct a previous
failed physical session, so automatic reload/retry remains prohibited and no
new CP trial is authorized on the post-panic unknown physical state. Native
Ubuntu baseline is restored with modem autoload disabled.


## 2026-11-19 — Build the modem overlay from tracked source

Closed a reproducibility gap: experimental modem kernel builds now compile
the tracked GPL device-tree overlay into the module package, with path/size/
SHA and source/Lineage attribution in the receipt. Optional explicit owner
stock BOOT input is validated and bound read-only; a cached image is never
silently adopted. Without that input the receipt says comparison not performed,
not hardware qualified. Existing audio/BT module shape remains compatible.

DTC output and full three-subtree comparison against the owner's manifest-
verified original stock BOOT/revision26 passed.6 package regressions and shell/
Python checks pass. Source-to-artifact-to-manual-guarded-stage instructions are
in MODEM_OVERLAY_BUILD.md. Build never stages, flashes or autoloads anything;
firmware/image publishing in CI remains disabled. No private stock BOOT or
firmware content is included in Git.

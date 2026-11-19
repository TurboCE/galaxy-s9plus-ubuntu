# Remaining kernel warnings through native44

Evidence date2026-11-19, one experimental SM-G965N rev26. The initial pair of observed native36
boots had zero error-priority lines and zero failed units; later trial results
and residual messages are recorded below.
This does not establish an error-free kernel or all hardware functions working.
The complete warning stream is preserved privately rather than suppressed.

| Warning class | Current evidence and limit |
|---|---|
| CPU feature sanity/unsupported variation |52 register-variation messages across heterogeneous cores in the latest warm boot. Common instruction/capability and cache semantics need SoC-specific review; no feature ID or warning mask was altered to hide them. Basic8-core/native-build proof is narrower than architecture/endurance qualification. |
| MAX77705 RGB/haptic missing OF node |One warning each. These functions remain unconfigured/unqualified; prototype source tests do not establish safe physical clock/current/supply behavior. |
| Alternate GPT |Read-only audit finds sda primary header and entries CRC valid, alternate header invalid at its expected in-range finalLBA; sdd primary/alternate headers valid. Logical sectors4096bytes. No partition-table writes. A reviewed metadata repair requires dedicated table backup/layout review and is separate from a driver fix. |
| Hub MCU_RESP reset uncertainty |One warning; real firmware readiness, pinned identity and accel/ALS feeds subsequently pass. A successful feed does not prove a hard reset or suspend/resume parity. |
| Bluetooth advertised transmit-power command unsupported |Existing board-scoped BROKEN_READ_TRANSMIT_POWER quirk is announced by hci_broken_table; hci_le_read_tx_power_sync skips that unsupported optional query. Keep the capability notice. Discovery/startup evidence does not establish pairing/audio or vendor-command parity. |
| Experimental module taint |Expected out-of-tree driver notice; not evidence of full functional correctness. |

Historical SSP zero-ACK retries remain in earlier boot records. Checked mode
commits only positively acknowledged bytes and latches exhausted/invalid streams;
latest observed36boots have no error-priority retry line and faultN. This does
not prove all transport modes or long-run end-to-end integrity. No kernel log
severity/filter was changed merely to achieve a clean error-priority snapshot.

On native44, a boot with a checked-transport delay of 4–5 ms before the
first write still logged a zero-byte response for a 36-byte write. The
sensor service recovered and acceleration and light values remained
readable. The original profile was restored and the same retry recurred
on the rollback boot. This first-write delay did not resolve the warning.

A separate native44 boot with opt-in short-ACK diagnostics put the
36-byte failure at transaction 455, attempt 1. MCU-ready was high,
previous credit was 12288 bytes, and the response reported zero status,
zero credit and zero acknowledged bytes. The checked retry path
recovered. Investigate the status transition or SPI response on that
transaction before changing retry or credit behavior.

The next native44 trial paired both responses of one transaction.
Its 36-byte first attempt returned zero status, credit and
acknowledged bytes. About 2.1 ms later the second attempt completed
all 36 bytes with status 0x16 and 12288 bytes of credit. MCU-ready
was high in both snapshots. The existing checked retry recovered;
the zero first response still requires investigation.

On a distinct native44 boot with transfer-length validation, the
controller reported the expected length even for the 36-byte write
whose acknowledgement required one retry. No controller error or
reported length mismatch occurred. Physical bus timing remains
unmeasured.

The opt-in matching native44 timing trial measured a 39.8 us SPI call
with a zero ACK, 49.249 ms since the preceding accepted write. Both
HOST_REQ samples were low and both MCU_RESP samples high. The first
retry succeeded and patch completion followed 146.8 ms later. This
was not an immediately adjacent transfer or a sampled GPIO change.
The observations do not resolve the remote firmware's state.

Another native44 boot requested SPI prescaler 7, but the controller
register read back zero. The 36-byte zero ACK and recovery recurred.
The changed module parameter did not verify a changed bus rate. The
Exynos9810 CHUB clock management divider was then independently read
and changed from field 0 to 1 on a bounded #44 trial. The same 36-byte
transaction needed two retries, with host-observed transfer times
comparable to the baseline and no direct SCK measurement. The trial
does not establish an effective bus-rate change or a fix for the
remaining zero ACK.

An independent warm boot with a 25 us SPI core chip-select setup
interval continued to get a zero ACK on the 36-byte write after
an accepted 14-byte transaction. The longer host-side SPI call
still needed one retry. This interval did not resolve the observed
failure.

In the firmware phase trial the zero ACK occurred 65.696 ms after
the loader's final firmware file read. All received SPI bytes
were zero, rather than just the status and ACK fields. The next
attempt accepted the complete write. The final file read does
not establish when the hub received its last firmware bytes.

A later native44 startup profile explicitly selects one standby
attempt. The driver still records a high MCU_RESP as an unconfirmed
reset. The sensor service continues to require the pinned hub
identity and fresh data after firmware startup. The profile reduces
startup delay on this handset. The first zero-ACK retry can still
occur and the physical reset behavior remains unresolved.

With desktop LTE enabled, native44 additionally records legacy SIPC
startup messages. The exact-module follow-up checks the initial memory
mapping and mailbox IRQ before using them. Known optional ECT and
packet-log paths no longer register false failures during startup.
Normal boot and LTE/Wi-Fi HTTPS204 passed with that module. The build
has no vendor ECT vote table, and the optional ACPM crash-dump region
remains unavailable. The observed ring still contained 103
error-priority messages and 67 warnings.

The native44 SBD diagnostics follow-up found 44 error-priority messages
from ordinary shared-memory ring and descriptor setup. Detailed offsets
now use debug logging without kernel addresses. The default log reports
the ring count and end offset on success, or the layout/initialization
stage and errno on failure. The detailed diagnostics require a debug-enabled
build on native44. Other SIPC and SSP messages still require review.

The native44 modem controller now distinguishes the verified PMU
reset configuration from an unsupported external reset GPIO and
validates both required interrupt numbers before registering either.
If a later registration fails it releases the interrupts already
registered and returns the original probe errno. A distinct device
boot registered both handlers, reached PIF_INIT_DONE and completed
no-SIM cleanup without the former invalid-GPIO error. Watchdog and
failure interrupt delivery were not induced on the handset.

Wi-Fi Direct IF_ADD timeout is separately repaired by a real firmware-backed
control context, with native boot/reboot, lifecycle/scans, existing STA HTTPS
and owner-assisted bidirectional discovery evidence in WIFI_DIAGNOSTICS.md.
A later native36 Fold7 group and source-bound 1MiB transfer in both directions
passed with matching hashes and preserved STA HTTPS204. The same boot now has
four error-priority lines: one SSP initial zero-byte write retry, two failed
action-frame retry batches while awaiting pairing, and one chanspec query -52.
Connection and cleanup eventually succeeded; these errors are not suppressed
or considered fixed by the transfer pass. No full Lineage parity is claimed.

A later opt-in modem probe exposed six IRQ_TYPE_NONE translation WARNs from
the legacy modem overlay. Read-only native GICD configuration showed actual
level mode for IRQ101/106/472. Explicit LEVEL_HIGH for those exact stock SPIs,
with a strict migration-aware stock verifier, passed a normal kernel36 reboot
and subsequent module probe with zero invalid-type/GIC-translate warnings.
This fixes the hardware description; active CP interrupt delivery is pending.

The chanspec query error was correlated with native P2P deactivation/deletion
in the previous boot. A source candidate now returns ENODATA for inactive P2P
client/GO state on star2/BCM4361/MSGBUF before querying firmware; active groups
and all primary/other-device queries retain the original path. C scope/state
tests pass. Native37 boot, Fold7 group, active channel query and bidirectional
1MiB hash checks passed. Actual group teardown produced zero chanspec errors,
with primary STA HTTPS204 preserved; one action-frame retry batch remains.
A cached-peer repeat failed discovery and is not counted as a connection pass.

Native38 sensor supply handling now checks ACPM transport/firmware failures
and mode readback before releasing the hub. Actual-C fault injection and
initial+normal warm native boots pass the normal path and fresh IIO feeds;
initial and warm error-priority streams each have zero lines. The MCU_RESP
warning still occurs and is retained: supply mode readback and successful
feeds do not demonstrate a physical hard reset or voltage measurement.

Use `scripts/g965n/kernel-health.py` with exact protected kernel receipt/
backup pins for new observations. Native38 journal retains111late lines
without the Linux boot header, whereas the ring retains694lines including
early boot. Journal-only absence is not evidence that an early warning is
gone. Native ring error-priority0, warning-priority64 includes52CPU variations
plus their unsupported-feature notice, cache hierarchy1, RGB/haptic2, GPT1,
4initramfs banners, taint1, Bluetooth quirk1 and hub reset1. The collector
preserves all original priorities/private raw logs and reports incomplete
coverage rather than asserting every hardware function is qualified.

Native41 is not error-free: initial ABOX send failures5/234 (ERAP extra) and
2/16 (PCM prepare) account for two error-priority lines and20IPC retries.
Later one-second silent playback and exact capture pass without new retries
or pointer stalls; this does not erase or repair startup errors. Sensor
held-state comparison39/40 failed to confirm the powered-CS hypothesis, so
41 restores the qualified control sequence and retains observations only.
MCU_RESP reset uncertainty and CPU/cache/GPT/unconfigured modules remain open.

Native42 corrects saved DSM diagnostic replay at the ALSA interface. The same
isolated old saved state sends one write ioctl on41 and zero on42, original
state unchanged. Initial plus distinct normal warm42 boots retain full early
rings: error0/warning64, audio retry counters0. This is bounded before/after
evidence, not proof that every possible ABOX timeout is eliminated.

Read-only42 cache audit exposes a concrete topology limitation: all eight
CPUs report L2 shared_cpu_list0-7; only M3 CPUs4-7 report L3 shared4-7. Cache
size/line/set/way fields are absent. The pinned SoC DT defines CPUs and a
cpu-map but no next-level-cache/cache nodes. In the actual built kernel,
cache_setup_properties failure selects use_arch_info, whose fallback assumes
all same-level caches above L1 are system-wide shared. This explains the
reported L2 map without demonstrating physical sharing. No cache geometry,
capability registers or scheduler topology is fabricated. A correction needs
SoC-specific cache ownership/geometry evidence before a DT change or reboot.

Native43 repairs the cache description using all8-core native42 architectural
measurements and primary Arm/Samsung ownership documentation (CPU_CACHE.md).
Initial plus distinct normal warm boots expose correct full geometry and
shared maps, remove the hierarchy warning without filtering, and retain
error0/warning63, fresh accel, three services and primaryHTTPS204. The prior
fallback L2 map0-7 is historical, replaced by A55 shared0-3/private M3 L2/
M3 sharedL3 4-7. The52 CPU feature-register differences and unsupported-feature
notice remain; cache metadata correction does not change those capabilities.

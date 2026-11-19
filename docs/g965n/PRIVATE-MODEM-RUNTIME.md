# Private modem runtime: stage, preserve and resume

This is an experimental SM-G965N-only manual procedure. Host tests and a
successful kernel build do not prove modem operation. This revision's provenance,
archive and resume paths are code-reviewed candidates until hardware validation
is recorded in CHANGELOG.md and VALIDATION.md. No service autostart is enabled.

Never mount or write the original EFS, CPEFS or RADIO. The helper reads their
labels, sizes and SHA-256 to establish that the verified backup and private
working copies belong to this handset. SYSTEM and VENDOR are mounted read-only
with `noload`. Only ordinary private RADIO files may reach the vendor runtime.

## Before a device change

Confirm SM-G965N on the connected handset, explicit owner consent, and a current,
complete nine-partition recovery backup (BOOT, DTB, DTBO, EFS, CPEFS, RADIO, MISC,
RECOVERY, PARAM). Verify every backup file against its recovery manifest before
continuing. `stage-modem` checks the complete manifest format and the actual EFS
and CPEFS images, plus current original EFS/CPEFS/RADIO hashes; it does not replace
verification of the other seven backup files. Preserve RECOVERY and the original
identity/radio partitions. Do not update or relock the bootloader.

Keep manifests, backups, extracted firmware, NV, archives, traces and journals
outside Git, under root-private storage on the owner's machine or handset. Never
publish their content or identifying values. The following paths are illustrative;
substitute the private verified paths locally. Do not paste secrets into issues.

Stop all modem clients before runtime migration. `run-ril-test.py`, `ril-lab.py`
and `run-cbd-test.py` now take a shared lease on
`/run/g965n-vendor-runtime.lock`; mutations take its exclusive lease. Both use
no-follow, non-truncating opens and check a private root-owned ordinary lock file.
CBD uses a separate `flock` monitor for its actual process lifetime, including
optional tracing outside the chroot. The monitor retains the lease even when
vendor code closes inherited file descriptors. After acquiring their own lease,
both children revalidate the exact parent-attested receipt SHA, private NV/RADIO
checksums, and current private mount inodes/read-only flags before opening modem
channels or executing vendor code. A queued service cannot silently accept a
new receipt published during the launch handoff. Original block-device access
is confined to the parent preflight and is never added to either child policy. Do not remove or replace
this lock file. Old versions of launchers must be stopped before migration.

## New private state

Run manually on the handset as root, with reviewed helper code and verified
backups copied to private paths:

```sh
python3 vendor-runtime.py up
python3 vendor-runtime.py stage-modem \
  --efs-backup /private/verified/EFS.img \
  --cpefs-backup /private/verified/CPEFS.img \
  --backup-manifest /private/verified/manifest.json
```

Stage refuses existing `efs`, `cpefs`, `RADIO` or `modem-provenance.json` entries.
It snapshots each no-follow verified input into a temporary root-only directory,
checks length and SHA-256, then preserves the complete extraction in a unique
root-only quarantine. The stock EFS diagnostic symlink at `cpdebug/node` is the
only reviewed exclusion from the separate working clone: its target is never
opened, and its original inode/link text remains in quarantine. The private
receipt records the excluded path, link-text SHA-256, source backup SHA-256 and
quarantine inventory SHA-256. Every other symlink or special inode aborts staging
before either working clone is created. Working clones contain ordinary files
and directories only. A root-private receipt
records same-handset provenance and the initial salted NV checksum. The original
identity filesystems are never mounted. Stage does not start CBD, RIL or radio.

## Legacy state: preserve before fresh staging

Receiptless copies are not automatically adopted. With all clients stopped and
all modem binds absent, explicitly preserve them:

```sh
python3 vendor-runtime.py archive-modem-state \
  --efs-backup /private/verified/EFS.img \
  --cpefs-backup /private/verified/CPEFS.img \
  --backup-manifest /private/verified/manifest.json \
  --confirm-archive-existing-private-state
```

The command preserves legacy state without adopting it: corrupt NV checksums,
empty files and a different ordinary RADIO image can be archived. It inventories
regular bytes by hash, symlink text by hash and special inodes by metadata only;
it never opens special inodes or follows links. Depth, count and byte bounds
still apply; regular hardlinks require manual review. RADIO and an optional
opaque receipt must remain ordinary files within their size bounds. It renames
the entire existing roots into a unique private archive and verifies content
hashes, link hashes, inode types, owner/group, modes and timestamps after moving. Archive content is preserved, never used as trusted
provenance. DATA is left in place. Then run the new `stage-modem` command above.
Do not delete an existing clone or archive to work around a validation failure.

## After a normal Ubuntu reboot

```sh
python3 vendor-runtime.py up
python3 vendor-runtime.py resume-modem
```

Resume requires the private provenance receipt, matching original partition
fingerprints, bounded ordinary NV trees, current salted NV MD5, and the original
private RADIO size/SHA-256. NV contents may legitimately evolve through the
restricted private RFS service; their size and salted checksum must still verify.
Resume binds those existing copies and reconstructs nodes/permissions without
extracting, replacing or deleting them. If TWRP or Android changes the original
partition bytes, stop for provenance review rather than relaxing the checks.

### Explicit primary-superblock maintenance exception

Ordinary `resume-modem` still rejects any original EFS hash drift. The separate
`revalidate-efs-superblock` command is a reviewed, explicit maintenance operation,
not automatic adoption or a replacement for the guard. It requires both the exact
old EFS backup named by the stored receipt and a newly verified complete
nine-partition backup, new EFS/CPEFS images and matching current hardware hashes.
CPEFS and RADIO must be identical to the old receipt, and bootloader provenance
must be unchanged. Originals must remain unmounted; clients must be stopped and
private modem binds absent under the exclusive runtime lease.

The only accepted EFS differences are the primary ext4 superblock fields at
absolute offsets 0x42c (4-byte mount time), 0x430 (4-byte write time), 0x434
(2-byte mount count), and 0x578 (8-byte lifetime write KiB). Both images must have
the ext4 magic. Every byte outside these four fields must be identical, including
all NV, inode, journal, backup-superblock and other metadata bytes. Values must
increase monotonically with no wrap: each timestamp delta at most 24 hours,
mount-count delta at most 4, lifetime-write delta at most 4096 KiB. Unknown drift,
clock rollback, counter overflow or larger intervals stop for manual review.

After operator review and explicit approval, with the private runtime up but no
NV binds or clients active, the command shape is:

```sh
python3 vendor-runtime.py revalidate-efs-superblock \
  --old-efs-backup /private/previous-verified/EFS.img \
  --efs-backup /private/new-verified/EFS.img \
  --cpefs-backup /private/new-verified/CPEFS.img \
  --backup-manifest /private/new-verified/manifest.json \
  --confirm-efs-superblock-revalidation
```

It snapshots verified input bytes, preserves the exact old private receipt under
a unique name, and atomically publishes a new receipt with old/new source hashes,
the new manifest hash, bounded-field proof and a history entry. Working NV,
RADIO, legacy archives and full extraction quarantines are checked unchanged.
It does not clone, archive, bind, resume or start a daemon. Only after successful
maintenance may the separately guarded `resume-modem` command be tried. At this
checkpoint maintenance has host-test evidence only; its live execution is pending.

Both test launchers additionally verify provenance, current NV and exact private
mount inodes, read-only stock SYSTEM/VENDOR and a read-only ordinary private RADIO
before unit/vendor launch. Keep `vendor-runtime.py` beside each launcher or provide its reviewed
path via `--runtime-helper`. This option must also work when tools are copied into
a private lab directory. Do not expand the inner RIL unit's device policy to
expose original block devices.

## Failures and recovery limits

On hardware, verify that CBD remains in the foreground under its monitor and
that the complete transient-unit cgroup is empty after its runtime bound. A
successful service-start request alone proves neither process lifetime nor
cleanup.

No automatic retry powers the CP or activates a PDP. A failed stage preserves
its complete source quarantine and any partial newly created files for explicit
review; the archive path can preserve corrupt state but never makes it trusted. A failed bind may leave
partial mounts; stop clients, inspect private evidence, and use `down` followed by
`up` before reviewed recovery. `down` refuses busy mounts and does not lazily
unmount them. Archive failures preserve moved bytes in their new location; do not
assume the original layout remains complete after a partial move.

## PDP qualification boundary

`experiments/modem/ril-lab.py` includes independent, host-tested reference encoders
and parsers based on Lineage samsung-ipc commit
`6d244414f7c66b0d0f93ef4b34f5276023408016` (`include/gprs.h`, `include/gen.h`).
That GPL-2.0-or-later protocol reference describes define=127, activate=103,
IP configuration=27 and status=4 bytes. The legacy profile remains unqualified
for S9 and is never connected to the S9 live path.

An independent examination of the owner's stock `libsec-ril.so` IpcProtocol41
and DataLink symbols established separate S9 wire facts: define=127,
activation=105, IP configuration base=157 or extended=257, and status=9 payload
bytes. The source candidate contains independent encoders/parsers and synthetic
fixtures; no vendor binary, disassembly, proprietary implementation or private
identifying data is redistributed. This is source evidence, not a hardware PDP
activation or internet result.

The initial S9 builder deliberately supports IPv4, CID1, no credentials and
zero reserved/auth/reason fields. Parsers reject every unqualified IP length,
wrong CID, invalid addresses, noncontiguous supplied netmask and out-of-range
MTU. They preserve unknown fields/flags and raw status/end-reason/throttle values
without guessing region-specific mappings or timer units. Each valid selected-CID
status event produces one protected private-journal record containing only the
raw state/end-reason, auxiliary flag/status and raw throttle timer, plus CID; no
raw packet or identifying values are included. Absent gateway and
mask remain absent; the stock implementation's guessed gateway and /24 defaults
are not automatically applied. IPv6 and P-CSCF fields are parsed as facts but no
IPv6 activation or IMS functionality is claimed.

Actual activation remains OFF by default. Only the two explicit switches
`--activate-pdp-s9 --confirm-reviewed-s9-pdp-layout` together can select the
candidate, after operator review and the existing root/model/backup/private-NV
checks. It additionally requires a recent complete CEREG registered status,
explicit APN/CID1 and a bounded deadline. A plan emits at most one activation,
requires matching define and activation acknowledgements plus active status and
valid IPv4 to report only `candidate-ip`, and never creates routes, assigns
addresses, changes DNS or reports internet verified. Exactly once after reaching
that state, the protected private journal receives only the selected IPv4, DNS,
gateway, prefix, MTU and CID fields for later owned-interface validation; no
APN, credentials, raw packet or device identifiers are included in that record. This path disables the old
CFUN4/1 retry. Registration loss, CP reset, malformed target messages or timeout
fail the plan. At deadline or ordinary termination it sends at most one
best-effort deactivate request if activation was attempted; that request is not
proof of acknowledged deactivation. A CP reset prevents stale cleanup to the new
CP. Service time limits and signal handling bound the lab lifetime.

These switches must not be used until the source candidate and its actual
hardware trial are explicitly approved. No PDP activation has been performed
at this checkpoint.

Even a registration acknowledgement and a candidate IP do not prove internet
access. Future testing must bind DNS queries and HTTPS to the owned rmnet device,
use bounded timeouts, preserve Wi-Fi/USB routes and DNS configuration, and remove
only routes it created. Verify DNS response and certificate-checked HTTPS before
marking data working. No calls, SMS, PIN or IMEI operations are part of this lab.

## Candidate changelog entry for integration

- Added private same-handset provenance, explicit content-preserving legacy
  archive and reboot resume; no automatic adoption, original partition mounts,
  daemon autostart or live PDP activation.
- Fixed mutable backup extraction input and opaque receipt preservation; added
  no-follow archival of legacy links/special inodes without executing them and
  complete extraction quarantine with the sole `cpdebug/node` working-copy
  exclusion. Working stage/resume still rejects all other links/specials. Added
  no-follow permission walks, lifetime migration/client locks, and child state
  revalidation after the asynchronous service-start handoff.
- Added pre-CP launcher provenance/private-bind/read-only RADIO checks and a
  source-qualified reference-only PDP planner; S9 wire-layout gaps fail closed.
- Host verification: 35 runtime tests, 6 launcher preflight tests, 4 reference PDP
  tests and 14 S9 candidate tests, Python compile and diff whitespace checks passed. Device archive/stage/
  resume and data connectivity still require separate recorded hardware evidence.

## Kernel 18 migration observations pending integration

The first device attempt stopped before archive/stage because the legacy STATE
parent was root-owned mode 0755. After no-follow FD/owner/type checks, only that
parent was tightened to 0700; DATA and existing clone ownership were preserved.
The next attempt prepared read-only runtime mounts, then stopped before any clone
rename because EFS contained a symlink. A read-only check of the verified raw
backup confirmed the same stock `cpdebug/node` symlink. Those failures motivated
the preservation-only archive inventory and the exact diagnostic-link quarantine
transform described above. The reviewed transform then passed on native kernel #18: complete legacy
archive and full raw quarantine inventories matched before/after, exactly the
reviewed diagnostic link was excluded from the ordinary working clone, current
NV salted checksum/private binds/read-only mounts verified, and original
EFS/CPEFS/RADIO SHA-256 still matched the fresh backup. STATE remained 0700 and
DATA remained 0755. These are hardware evidence for archive and fresh staging;
reboot resume and bounded daemon lifetime still need their own checks. No CP,
CBD, RIL or PDP was started during migration or its verification.

## Kernel 19 CP-start failure and source guard candidate

The explicit kernel 19 superblock maintenance and existing-copy resume passed on
hardware: the old receipt was preserved, working NV content stayed unchanged,
archives/quarantine inventories matched, and original source hashes matched the
fresh backup. The exact kernel 19 modem module and character nodes then loaded.

The single approved bounded lab did **not** reach PDP activation. Its recovered
journal contains no transmitted IPC configuration, AT command, RFS reply or PDP
candidate. CP startup panicked the AP and recovery booted. Private pstore shows a
failed initial reset-assert wait, then a failed CP-init pending-interrupt wait.
The old driver ignored those errors and marked initialization complete, issued
security mode 2, received a vendor status, and entered normal-mode security before
an asynchronous SError. The normal-mode firmware sizes/addresses matched earlier
successful startup logs. The PMU register sequence and 1 ms waits match Lineage;
the reason the cold handshake failed is still unresolved. Unconditional initial
OFF against an uninitialized CP is a hypothesis requiring separate review.

The source-only guard candidate now propagates checked PMU errors, serializes
security and all process power/reset/dump transitions with one mutex, and uses
IRQ-safe atomic invalidation for watchdog/failure/unexpected offline events.
Only a completed verified reset without a new fatal IRQ clears the failed
session. Expected offline completion is recognized during an explicit reset or its
graceful shutdown wait; watchdog/failure IRQs remain unconditional faults. RAM-logging security requests use the same gate. An optional probe logging
request before the first CP initialization returns deferred (`-EAGAIN`) without
clock/security calls or a new failure latch; it cannot cold-start the CP. Existing
failure/IRQ latches remain blocking. Secure CTRL
write failures of either sign are rejected. Internal clock/PMU failures return
negative errors and clock disable is attempted on all paths after enable was
attempted. The original clock-before-secure-CTRL-init order is preserved.

The owner's CBD independently confirms that mode 2 preserves nonnegative vendor
stage status and tests only its sign; those returns remain unchanged. Negative
failures and normal/dump/logging verification errors latch the session closed.
Neither firmware validation nor secure-monitor parameters are bypassed or changed.

Host qualification compiles the actual production C functions with faultable
PMU/SMC stubs and a real pthread mutex: 21 scenarios cover initialization/reset
failure propagation, zero security calls after failed PMU readiness, clock error
normalization/cleanup, vendor mode-2 ABI preservation, terminal error latching,
IRQ invalidation, verified-reset recovery, and concurrent power/security exclusion.
This is a containment candidate, not a demonstrated cold-boot fix. No further CP
trial is authorized by a successful build or these host tests. Manual module
reload alone does not prove physical readiness or retain a previous failure's
history; automatic reload/retry remains prohibited.

### Owner CBD startup control flow

Independent analysis of the owner's CBD establishes its Shannon310 startup
sequence: query the modem status, skip RESET when the raw status is zero, or
request RESET when nonzero; then security mode 2, firmware transfer, normal
security mode 0, MODEM_ON and the boot handshake. Mode-2 nonnegative status
continues the original flow; negative errors abort. The parent launcher's extra
unconditional preliminary OFF was removed so the owner's status-dependent
sequence remains in control. All existing private provenance/bind checks still
precede unit/vendor launch. No new cold-launch option or forced reset fallback
was introduced.

This removes a source-proven extra mutation; it does not establish physical cold
state, explain every PMU handshake failure or prove a successful cold boot. The
software OFFLINE value is initialized by the driver and cannot independently
prove hardware power state. After the panic, a new CP trial still requires a
separately approved fresh physical cold/proven handoff condition; no automated
retry, reload or reset is authorized.

### Several archived recovery checkpoints

Repeated recovery boots can accumulate more than four EFS mount-count updates
between modem tests. The ordinary one-hop check still rejects this. An explicit
maintenance invocation may additionally repeat `--intermediate-backup-manifest`
in chronological order, pointing to one to seven archived complete same-handset
nine-partition manifests; each directory must contain its matching `EFS.img`.
Before uploading selected evidence, verify **all nine files** of each chosen
backup against its manifest on the host. The exact old and final EFS snapshots,
final CPEFS and final manifest are still mandatory.

Every adjacent snapshot must independently pass the original four-field proof,
including at most four mount-count changes per step. Every checkpoint must have
the same bootloader and unchanged CPEFS/RADIO fingerprints. No bytes outside the
four primary-superblock fields may change, even temporarily in an intermediate
snapshot. The total timestamp/write-counter differences still fit the original
24-hour/4096-KiB limits; a chain cannot multiply those budgets. Duplicates,
incomplete manifests, different hashes/handsets and missing checkpoints fail.
The receipt records checkpoint manifest/image hashes and each proof; all old
receipt, NV, RADIO and quarantine preservation checks still run. No original
partition is mounted or modified, and this operation does not start the CP.

### Attach to an already-online CP

The bounded RIL launcher supports `--attach-online`. The parent and child both
read IOCTL_MODEM_STATUS and require exactly STATE_ONLINE4. This path starts no
CBD and requests no CP reset; the child queries SIM status and establishes AT
readiness before its existing explicit radio/PDP gates. Keep the modem runtime
lease and private provenance checks. The sensor supervisor intentionally owns
a sensor-only runtime and refuses modem nodes/bindings, so stop it for a modem
trial; prepare the modem runtime under the exclusive lease, resume verified
copies, run the bounded client, ensure its cgroup/lease ends, tear that runtime
down, then restart the sensor service. Do not attempt to share an unrestricted
vendor runtime or bypass either service's device allowlist.

The current KT LTE trial APN follows [KT's published settings](https://ermsweb.kt.com/search/faq/faqAnswerM.do?kbId=KNOW0000270915&nodeId=NODE0000000509&parentNodeId=NODE0000000494).
Carrier-specific values are an explicit local test input, not a guarantee that
all SIM plans or other carriers work. A registered CP or candidate IP still
requires independent interface-bound packet/HTTP/DNS evidence.

The native KT radio-on path now uses the own-vendor builder's command0107,
EXEC1 and payload0202, after profile acknowledgments/AT readiness. This changed
observed phone state1→2; AT CFUN1 had acknowledged without establishing that
transition. No automatic CFUN4/1 retry remains. The independent reference
[pwr.h](https://github.com/LineageOS/android_external_libsamsung-ipc/blob/6d244414f7c66b0d0f93ef4b34f5276023408016/include/pwr.h)
corroborates the normal state value, while S9-specific packet facts come from
the owner's stock RIL. Other carrier/property variants are not qualified by the
KT result. Registration remained searching; this is not LTE internet proof.

For an explicitly reviewed initialization trace, `--capture-private-rfs` records
only bounded RFS OPEN/CLOSE frames in the root-private lab directory. NV payloads
are excluded, original files are never opened through these requests, and the
current handler still refuses remote filenames. The capture itself can contain
sensitive filenames: never commit/publish it. This is diagnostic evidence for
reviewing a future fixed, read-only allowlist, not such an allowlist already.
Status diagnostics redact subscriber/device identity response fragments before
journaling; they retain only the home network prefix or format-validity booleans.

### Identity diagnostic privacy and limits

The bounded CGSN diagnostic never journals raw response fragments. It reports
only format/Luhn validity and default-value classification. An unknown reply
can also expose fixed booleans and at most eight numeric-field lengths, never
identity digits or hashes. The parser accepts exactly one whole14..16-digit
field in a completed response, rejects ambiguous/longer fields and terminal
errors, and never gates radio/PDP operations. Native37 verified a valid
nondefault identity classification and absence of identity digits in its
private journal. This is not network authorization or LTE data evidence.

### Bounded operator scans and rejection diagnostics

`run-ril-test.py --attach-online --observe-only --scan-networks --seconds 120`
requests one AT COPS test; `--scan-networks-s9` instead uses the owner's stock
bodyless0804 GET2. Both forbid radio/PDP configuration and require at least
110seconds. Samsung scan uses the matching stock0804 SET3 cancel only if its
request remains pending at90seconds/cleanup. A rejected request is terminal;
it does not trigger cancel/reset/retry. Scan summaries expose counts only,
never operator names/PLMNs. Exact count/size is required for the stock10-byte
entry layout. Native37 rejected AT scan and Samsung GET (raw generic100), so
no actual operator-list/coverage pass is claimed. The official
[ModemManager scan guidance](https://www.freedesktop.org/software/ModemManager/man/latest/mmcli.1.html)
explains why a scan needs a longer time allowance; any bounded timeout remains
inconclusive.

Native37 numeric-only registration diagnostics include cause byte10 of the
body, verified against the owner's NetRegState constructor and Lineage net.h.
The captured getter returns raw cause6. The
[AOSP registration causes](https://android.googlesource.com/platform/hardware/interfaces/+/a714c08e8f0a9981c629607ce58dc318da879095/radio/aidl/android/hardware/radio/network/RegistrationFailCause.aidl)
and [ETSI TS24.008](https://www.etsi.org/deliver/etsi_ts/124000_124099/124008/18.06.00_60/ts_124008v180600p.pdf)
name6 Illegal ME. Treat network-side equipment refusal as a hypothesis until
the relevant domain/procedure and same-handset Android/network history are
corroborated. No identity alteration or forced CP recovery follows this code.

Final owner/device clarification: **S9+ has a physical SIM inserted**. The
preceding no-USIM/prior-stock-use statement referred to S8+ and must not be
applied to S9+. Previous stock-Android LTE use of this exact S9+ is unknown.
Physical insertion does not independently prove readiness, service eligibility
or registration. No blacklist/settings conclusion follows the recorded cause.

### Native43 EPS diagnostics and remaining file/QoS gaps

The read-only `AT+CEREG=?` capability query is required before considering
extended reporting. The [2018 AT specification](https://www.etsi.org/deliver/etsi_ts/127000_127099/127007/14.08.00_60/ts_127007v140800p.pdf)
describes optional extended reporting, but this owner's modem actually returns
only modes0,1,2. Do not blindly send mode3 based on a generic modem guide.
The new decoder returns numeric status/optional reason fields, drops cell/
tracking-area/timer values, and changes the initial-PDP gate only after a
complete acknowledged own query. Mode3/extended-URC streaming was not enabled
or qualified. Native43 stays in searching state2, with no PDP/data pass.

The fresh native run verifies ready state survives phonebook completion130/131;
SIM readiness alone is not network registration. The same bounded experiment
exposes missing ECT frequency tables, no-op vendor bus QoS, optional packet-log
failure and shutdown-channel demux messages. Vendor error-priority dumps are
not automatically fatal, but the loaded-modem log is not called clean.
The existing CBD monitor expires at90s; a120s RIL observation must not describe
that monitor as continuously running or an exit0 job.

The private RFS implementation denies modern file OPEN/CLOSE. It currently
cannot collect requested modem reject-diagnostic files or provide missing
CP audio files. Their exact framing/semantics and a confined private namespace
need review; never expose host paths, original partitions or invented content.
Raw captures, files, NV and all owner vendor binaries remain private. A normal
guarded reboot returns the unqualified CP module to its opt-in-off baseline.

### Bounded modern diagnostic file experiment

`run-ril-test.py --serve-private-rfs-diagnostics` is opt-in and creates a new
`rfs-diagnostics` directory inside the private lab. Keep it out of Git: its
contents may identify networks or equipment. It is not an EFS substitute.
Only exact CP names `err/csdiag_mmrj_Info.dat` and `err/csdiag_rf_Mipi.dat` map
to fixed new lab files. No missing CP audio/default/identity file is invented.
The default continues to deny OPEN/CLOSE. Existing diagnostic output is never
reused: repeat trials require a fresh lab directory. The bounded namespace
implements commands3/4/5/6/17; others fail closed. OPEN flags0/66 only; seek
supports the owner's nonnegative32-bit offset interface within256KiB. Host
wire/isolation tests alone are not a successful CP file round trip or LTE
qualification. No proprietary implementation or disassembly is redistributed.

Native43 qualification: CP OPEN/SEEK/WRITE25bytes/CLOSE succeeds for RF
diagnostic; network-reject file not requested, READ remains host-only tested.
LTE still searching; no data qualification. Private evidence retained off Git.

### Cold-test RF quiesce before channel close

Use `--quiesce-radio-on-exit` for a bounded cold configuring trial that is
ending, rather than intentionally leaving RF active for another observer. This
option is refused for existing-online or observe-only attachment. It requests
SIPC RF low power once, continues servicing private RFS and IPC, and waits for
an exact LPM phone-state response plus a two-second tail inside a ten-second
bound. Generic acknowledgement alone does not qualify. No fallback reset,
secure-monitor operation or physical power-off claim is added. The unit gets
fifteen seconds of cleanup headroom. Startup, rejection or timeout failures are
retained; the normal modem-off cleanup reboot remains separately guarded.

Native43 cold90s trial confirms LPM and two-second tail with8frames. One
delayed IPC-not-open and one startup RFS-not-open remain; physical CP shutdown
and loss-free channel lifecycle are not qualified. LTE remains unresolved.

### Readiness before vendor startup

Launcher uses a main-process `Type=notify` service. The child reports readiness
after checked private state, all three modem descriptors, buffers and cleanup
handlers exist. Parent requires notify/active/running/nonzero main PID within
ten seconds before starting CBD. An asynchronous start-job reply or an ordinary
simple service is insufficient; failure stops the child without vendor launch.
Native43 verifies this ordering. It does not qualify continued daemon liveness
or repair LTE. The initial `shmem_init_comm` peer-wait message is emitted before
the paired descriptor opens and returns0; it is distinct from dropped incoming
packets in `rx_demux`. Do not diagnose packet loss from that message alone.

### Shared-link boot completion ordering

The modem candidate defers open-side INIT_END while the link is OFFLINE.
CP_START resets shared memory first, sets IPC state under the state lock, writes
the existing clock-table header, then acknowledges if both userspace endpoints
are ready. A pair opened later completes under the same lock. Boot-on clears
link state/completion together. This does not provide missing ECT frequencies
or bus QoS; no invented table is used. Existing CP_START acknowledgement
retransmission is retained. Native43 module-only early-open trial validates the
CP_START -> clock header -> INIT_END sequence; late-open permutations also have native STATUS4/observe-only link-handshake
proof. A queued retry is acknowledged; RF remains low-power in that case. Ten
RFS requests after the bounded client closes are still unhandled, so persistent
file servicing/physical shutdown is not qualified. Baseline immutable startup
package remains preserved with modem default off; trial candidate stays private.

### Correct IPv4 attach mapping and actual data path

Review both boundaries: owner string `IP` maps to internal DataProtocol1;
`IPV6` maps to2; `IPV4V6` maps to3. The attach wire mapper yields2,5,6 for those
three values. The earlier helper wrongly called wire5 IPv4. Home and roaming
attach fields must be2 for this bounded IPv4 profile, matching the PDP definition
wire2. Prior tests repeated the wrong assumption; they now cover this boundary
and cross-message consistency. No owner implementation/disassembly is published.

With the personal KT SIM, this correction registers EPS1 and activates CID1.
Modem-assigned IPv4/DNS/MTU is not itself Internet proof. The separate
`test-pdp-data.py` requires a still-active, exact RIL invocation and live
candidate, reviewed model/BOOT/backups, consent and an initially unused rmnet0.
It binds DNS/TCP sockets to both the modem address and device, uses only supplied
DNS, verifies TLS hostname/certificate and requests a fixed HTTPS204 endpoint.
It adds only temporary /32 host routes; no default route or invented gateway.
The local /32 interface assignment is a point-to-point host address, not a claim
that the modem supplied a prefix. Cleanup requests and actual restored state are
reported separately. Keep all private candidate/log files out of Git.

Native43 passes modem DNS, verified HTTPS204, RX10/TX9 and0interface errors,
with temporary routes/address/link/MTU restored. This is a bounded data trial,
not an always-connected deployment or IPv6/voice/SMS qualification. Current
kernel lacks IP_ADVANCED_ROUTER/multiple-table support (`ip rule` unsupported);
first policy-route preflight made no changes. Host-route testing succeeds while
Wi-Fi/default routing remains available. Persistent bearer/network integration,
advanced routing configuration and file-service/shutdown lifecycle remain work.


An already-attached CP can report EPS1 and a completed `AT+CGATT?` value1/OK
while an explicit PS-attach SET returns raw0x8005. That raw result is not decoded
or treated as an ACK. The PDP gate can instead use a completed, echoed,
unambiguous attachment query1/OK no older than15seconds, with the existing
fresh registration/SIM/radio/AT conditions. A negative/invalid reply clears that
query path and CP boot resets it. Polling remains bounded and PDP-opt-in only.
A distinct native cold run repeats actual DNS/TLS204 and live query parsing;
that run had a successful SET ACK, so the no-ACK alternative still needs a
matching hardware scenario. No automatic reset loop or persistent service is
introduced by this change.


### Bounded LTE with the sensor service running

The guarded test harness can select the fixed modem view with
`select_modem_runtime()` before using the runtime helper. Prepare the view
and resume the verified private modem copies under
`modem_runtime_setup_lock()`, using the normal model, BOOT, backup and
module checks. Pass `--isolated-modem-runtime` to `run-ril-test.py` with
the same reviewed runtime helper. Both launchers and their child
processes select the corresponding view. Stop the bounded clients
before taking the setup lease for teardown of the modem view.

The modem view uses a separate mount tree and scratch data directory.
It shares the original private NV state and the lease that excludes
legacy NV maintenance. The sensor view retains its existing mount tree
and does not expose modem nodes or NV. The modem process device policy
remains closed. The existing shared lease means the sensor service
should stay running throughout the bounded test; its startup and
teardown still require that lease exclusively. Restarting the sensor
service independently while LTE stays active is unqualified.


For a pinned sensor profile with `runtime_view` set to `isolated-sensors`,
the sensor supervisor uses its own mount tree, scratch directory and lease.
The prior restriction on sensor restart while the modem holds the shared
NV lease applies to the legacy view. Native43 completed a sensor restart
and restored sensor feeds while the same bounded RIL/PDP session continued
to carry actual data. Use the dedicated view for independent service
lifecycles.


### Bounded held context

`--hold-qualified-pdp` requires the explicit PDP switches and a cold trial
with `--quiesce-radio-on-exit`. A qualified context remains available through
the bounded service window while SIM and AT readiness and fresh registration
continue to hold. A route-relevant IPv4 configuration change invalidates the
context. The activation deadline is still enforced until qualification. On
native44 this was verified by two policy-route DNS/HTTPS probes in the same
context, with the second 27.1 seconds after initial qualification, beyond
the 20-second activation limit. There is no automatic retry in this mode.

The qualified held-context teardown can distinguish the PDP release reply
from the subsequent LPM sequence. On the tested native44 CP, release
returned generic success 0x8000 and reported state 3 for the same CID
within three seconds, followed by a separate successful LPM response.
The reported state is retained as a raw firmware value.


### Explicit one-shot reconnect test

For a held cold trial using the isolated modem runtime, add
`--cycle-qualified-pdp`. After source-policy probe 1 returns with the previous
route state restored, create the empty root-private `cycle-requested` marker in
the validated lab directory. The RIL invalidates generation 1 and observes the
release before considering a new activation. Reuse requires the tested success
and same-CID state, as well as new CEREG and CGATT replies after release. Use
`--pdp-generation 1` and `--pdp-generation 2` for the two network probes. The
marker is processed at most once. This test does not trigger on unplanned loss.


### Ordinary-app IPv4 fallback trial

With the running, qualified held cold trial, use the existing guarded
network helper with `--wifi-fallback-usb-peer` set to the direct USB
management peer. This explicitly interrupts the active Wi-Fi connection
for the trial and requires the original Wi-Fi default and profile. The
probe uses a higher-metric modem default and restores the original state.
During Wi-Fi absence it uses the interface's supplied DNS configuration and
checks an uncached system query plus a nonroot curl request without interface
binding. The native44 result was Wi-Fi → LTE → Wi-Fi, with verified
HTTPS204 and no modem interface errors. This manual trial does not install
a network manager or an automatic connection service.


### Lease-driven IPv4 route owner

The guarded isolated held trial supports `--export-ipv4-lease`. Its RIL
publishes the currently qualified IPv4 parameters on tmpfs with a short
expiry, and withdraws the lease before releasing or stopping a context.
A separate root process running `lte-route-owner.py --invocation ID
--confirm-guarded-g965n-route` checks the exact live lab invocation and
owns the standby default on rmnet0. Launch it after, and bind its lifetime
to, the RIL unit. System resolver changes follow selection of the LTE
default. This keeps packet-path setup outside the RFS event loop. Do not
run the temporary network probes concurrently with the owner.

Native44 verified default failover and DNS withdrawal, independent sensor
operation, and route replacement and cleanup across a commanded PDP
cycle. The bounded process does not install a boot unit. Use the
same trusted route-owner executable and invocation with `--cleanup` as
the unit's `ExecStopPost` handler. Native44 verified that systemd removed
the modem route, address and DNS after actual SIGKILL of the worker. This
exercises crash cleanup, without testing automatic process restart.
Persistent operation and unattended radio loss are open.

### Explicit one-shot boot qualification

The [unit example](profiles/lte-boot-test.service.example) shows the exact
boot ordering and the 175-second supervisor limit used on native44. It is
not installed by the image build. Use a dedicated root-owned mode 0700
directory under `/var/lib/g965n-lte/` and keep the runtime profile, APN,
backup and boot receipts private. Copy these reviewed files into the
directory:

- From `scripts/g965n/`: `lte-boot-session.py`, `run-ril-test.py`,
  `run-cbd-test.py`, `vendor-runtime.py`, and `lte-route-owner.py`.
- From `experiments/modem/`: `ril-lab.py` and `rfs-copy.py`.

The root-owned private `config.json` contains `model` (`SM-G965N`),
`apn` (the reviewed carrier APN), `kernel_profile` (the absolute
directory with `startup.json`, `backup.json`, and its qualified
`package/`), `receipt_sha256`, `backup_sha256`, `guard_sha256`
(the pin of `package/p2p-control-trial.py`), and `files` (the SHA-256
map of the seven copied source files). Replace the example unit's
config digest placeholder with the exact digest of this private file,
and its directory if needed. The installed kernel, phase-tested module
and stock overlay must match their existing receipts. Private modem NV
must already be staged and verified using the normal procedure.

After inspecting and verifying the proposed unit, arm it with the root-owned
contents `armed\n` in the file named `armed`, enable the unit for one boot
without `--now`, and reboot in the approved device test. The arm is consumed
before the controller loads the modem, and an attempt latch prevents a
second cold start on the same boot. Stop and disable the unit afterward.
The modem module is left loaded until a normal reboot. Do not unload it
while the CP is live. Native44 boot-state and unbound traffic probes
qualified this one-shot path; continuous operation is separate.

### Longer boot qualification and Ubuntu Mobile Network

For the explicitly bounded extended test, append `--soak` to the guarded
boot controller, and set the unit's `RuntimeMaxSec=360`. The isolated held
RIL is limited to 300 seconds, with 315-second outer bounds for the boot
companion and route worker. Native44 passed actual LTE-bound DNS and TLS
at 26.0, 135.7 and 270.7 seconds in the same RIL session, then naturally
released and cleaned up. The normal default remains 120 seconds.

The Ubuntu packages `modemmanager` and `mobile-broadband-provider-info`
were installed on the test device and ModemManager enabled. Stock
`mmcli -L` still returns no modems with the native driver loaded.
[GNOME 46's WWAN panel](https://github.com/GNOME/gnome-control-center/blob/gnome-46/panels/wwan/cc-wwan-panel.c)
uses supported devices from ModemManager's object manager.
The [upstream Samsung plugin](https://raw.githubusercontent.com/linux-mobile-broadband/ModemManager/main/src/plugins/samsung/mm-plugin-samsung.c)
matches a limited set of USB tty/net products. This handset needs a
Samsung IPC control adapter, along with a handoff of the qualified
bearer to NetworkManager. Only one owner should issue modem control
commands or configure the same bearer at a time. The existing LTE
path is verified independently of the standard desktop panel.

### Physical grouping for a native modem adapter

The optional `link_wwan_parent=1` module parameter attaches only
`umts_router` and `rmnet0` to the real `mif_sipc5` platform device. The
shared parent gives discovery code a hardware anchor. It passed native44
LTE data and independent sensor operation. The raw control port still
belongs to the miscellaneous subsystem. Stock ModemManager does not
handle this Samsung SIPC device after grouping, and no generic probe
tags have been added.

Reviewed the exact Ubuntu Noble 1.23.4-0ubuntu2 source. Its
[ModemManager port-detection model](https://modemmanager.org/docs/modemmanager/port-and-device-detection/)
groups kernel ports into devices before plugin selection.
The native adapter still needs a supported control endpoint and a
bearer handoff to NetworkManager. The stock generic modem must not
independently open the lab's router channel while the SIPC owner is
running. Qualification requires real modem enumeration, controls and
data from the Ubuntu mobile network path.

### Typed WWAN queries through the existing radio owner

Add `--wwan-query-broker` to the guarded isolated held RIL trial to bind
`/run/g965n-wwan-<RIL InvocationID>.sock` as a root-only Unix
`SOCK_SEQPACKET` endpoint. A connection sends one literal request and
receives one JSON reply. The request names are `registration`,
`packet-attachment`, and `signal-quality`. Results use the raw modem
registration or RSSI code, or the confirmed packet-attach boolean.
Unsupported commands, stale requests and modem errors return an
explicit error. The broker serializes its requests with the current
radio owner instead of opening another physical modem channel.

### Explicit IPv4 data control for a native modem adapter

Add `--wwan-bearer-control` together with `--wwan-query-broker` and
`--export-ipv4-lease` to the guarded held trial. This mode cannot be
combined with the legacy one-shot reconnect marker. The radio registers
and attaches to packet service as usual. The data context waits for an
explicit `connect-ipv4` request.

`bearer-status` returns a state and the current data generation.
`connect-ipv4` is valid in `idle` and `disconnect-ipv4` in
`connected`. A reply with `accepted: true` confirms the request was
accepted for the reported generation. Poll for the corresponding
`connected` or `idle` state to verify completion. The control path
withdraws the lease at disconnect and requires a successful release
acknowledgment and inactive status on the matching context before
reporting `idle`. A subsequent connection waits for fresh registration
and packet-attach reports. A `connected` state means the modem issued
qualified IPv4 configuration. The client must use the current lease and
check actual traffic separately.

These requests provide the modem side of an adapter. The ModemManager
device and the NetworkManager handoff still need implementation.
NetworkManager and the standalone route worker must never own the same
bearer's routes or resolver configuration at the same time.

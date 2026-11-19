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

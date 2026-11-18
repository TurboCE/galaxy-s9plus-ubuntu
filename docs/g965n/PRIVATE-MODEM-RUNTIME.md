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
checks length and SHA-256, then extracts only that snapshot. A root-private receipt
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

The command currently requires complete, logically valid NV and a matching
ordinary RADIO copy. Corrupt or incomplete legacy state fails closed for manual
review. It renames existing clones and an optional opaque receipt into a unique
private archive; file content hashes, owner/group, modes and timestamps are
verified after the move. Archive content is preserved, never used as trusted
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

Both test launchers additionally verify provenance, current NV and exact private
mount inodes, read-only stock SYSTEM/VENDOR and a read-only ordinary private RADIO
before CP I/O. Keep `vendor-runtime.py` beside each launcher or provide its reviewed
path via `--runtime-helper`. This option must also work when tools are copied into
a private lab directory. Do not expand the inner RIL unit's device policy to
expose original block devices.

## Failures and recovery limits

On hardware, verify that CBD remains in the foreground under its monitor and
that the complete transient-unit cgroup is empty after its runtime bound. A
successful service-start request alone proves neither process lifetime nor
cleanup.

No automatic retry powers the CP or activates a PDP. A failed stage preserves
its partial newly created files and may require explicit review because the
normal archive path requires complete valid state. A failed bind may leave
partial mounts; stop clients, inspect private evidence, and use `down` followed by
`up` before reviewed recovery. `down` refuses busy mounts and does not lazily
unmount them. Archive failures preserve moved bytes in their new location; do not
assume the original layout remains complete after a partial move.

## PDP qualification boundary

`experiments/modem/ril-lab.py` includes independent, host-tested reference encoders
and parsers based on Lineage samsung-ipc commit
`6d244414f7c66b0d0f93ef4b34f5276023408016` (`include/gprs.h`, `include/gen.h`).
That GPL-2.0-or-later protocol reference describes define=127, activate=103,
IP configuration=27 and status=4 bytes. It does not establish the proposed S9
105-byte activation / 257-byte IP layout. The reference planner is deliberately
not connected to the live loop, and S9 activation remains blocked until primary
source or reviewed hardware traces establish the exact target layout.

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
  no-follow permission walks, lifetime migration/client locks, and child state
  revalidation after the asynchronous service-start handoff.
- Added pre-CP launcher provenance/private-bind/read-only RADIO checks and a
  source-qualified reference-only PDP planner; S9 wire-layout gaps fail closed.
- Host verification: 24 runtime tests, 4 launcher preflight tests, 4 reference PDP
  tests, Python compile and diff whitespace checks passed. Device archive/stage/
  resume and data connectivity still require separate recorded hardware evidence.

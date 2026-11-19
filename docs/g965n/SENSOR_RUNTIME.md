# Gated sensor-only runtime supervisor (source candidate)

This is source-only until the complete private profile, modules, units and
startup/stop behavior receive separate hardware review. It does not install or
enable a service. It never starts CP/CBD/RIL, resumes modem state, mounts EFS,
CPEFS or RADIO, changes protected partitions, reloads/unloads a module, or
restarts an application/portal. Initial policy is `Restart=no`.

Device-node creation is part of the service device policy: the initial closed
policy intentionally allows no sensor `mknod`. Temporary exact `rwm` is granted
only after host nodes exist, then reduced to `rw` before children. The existing
generic vendor-runtime default still creates its devices; only the new sensor
service opts out during the initial mount phase.

## Contract and lifecycle

One `g965n-sensors.service` supervisor owns startup and ordered shutdown:

1. Verify the root-only profile SHA, model, exact original startup receipt,
   actual BOOT/kernel through the existing pinned verifier, complete nine-partition
   backup manifest, every program/module/firmware hash, and acceleration policy.
2. Require the service's actual MainPID, cgroup and closed device policy. Take
   the instance lock and canonical vendor-runtime exclusive lease nonblocking.
   An existing shared/unowned runtime is preserved and refused. A stale runtime
   can be cleaned only with the exact private ownership receipt, boot/profile/
   mount fingerprints and quiescent recorded cgroup.
3. Prepare SYSTEM/VENDOR `ro,noload` through
   `prepare(sensor_only=True, create_devices=False)`. This first phase mounts
   the read-only runtime without creating any device nodes. Verify the owner's fixed
   `vendor/bin/hw/lhd` and
   `vendor/etc/sensor/lhd.conf` hashes before module hardware access.
4. Load each missing transport/IIO module at most once. Reuse an existing module
   only when its loaded ELF build-id note and required read-only parameters
   match; otherwise preserve and fail. There is no reload fallback. Reject NV binds, `/dev/block` or modem nodes in the runtime.
5. After the modules create their host character nodes, verify the current
   service MainPID/cgroup again and apply an exact temporary `rwm` allowlist
   through structured systemd `SetUnitProperties`. Only then create the fixed
   sensor/basic character nodes inside the runtime. A `finally` block shrinks
   the same exact character-node entries to `rw`, including failed node setup;
   either child is forbidden to start before that shrink succeeds. Keep
   BOOT/SYSTEM/VENDOR permissions at `r` in both phases. Never grant
   `char-misc`, EFS, CPEFS, RADIO or modem device access.
6. Atomically downgrade that same lease FD to shared; the supervisor holds it
   through both children's actual lifetime. Start the fixed owner lhd command
   and exactly one pinned SSP broker. The lhd child enters the chroot, moves
   its working directory, sets no-new-privileges and drops its complete
   capability bounding/permitted/effective/inheritable sets. The broker retains
   the CAP_SYS_ADMIN required by the IIO bridge's open/write checks.
7. Accept `READY\n` through the dedicated passed pipe only after the broker has
   checked hub identity/mask/range as applicable and published its first real
   enabled frames. Only then notify systemd READY. Child exit or readiness
   failure fails the service; no automatic hardware retry occurs.
8. On STOP/SIGTERM/failure, send the broker `STOP\n`, let it disable every enabled
   sensor with bounded transactions and close its SSP/IIO FDs, then stop lhd.
   Attempt lhd shutdown even after a broker cleanup timeout. Confirm both
   children exited before exclusive-lease cleanup. A live child, foreign lease,
   ownership mismatch or changed mount tree preserves the runtime and reports
   failure. No lazy/forced unmount or module unload is used.

A private cgroup/baseline-process receipt also prevents a later stale-cleanup
attempt from unmounting underneath unconfirmed children left by an abruptly
killed supervisor. Unexpected partial mounts before an ownership receipt is
written are preserved for manual review. A bounded cleanup failure is never
reported as sensor shutdown success.

The service deliberately does not request a separate mount namespace:
canonical runtime mounts and lease tools must describe the same mount tree.
Do not casually add `ProtectSystem`/`ReadWritePaths` settings that implicitly
create another namespace without redesigning ownership and maintenance checks.
Lhd is restricted separately by its chroot, dropped capabilities and the
service's exact device policy.

## Private profile schema

All paths must be absolute root-owned ordinary files under ancestors not
writable by other users, with no symlink ancestors. The profile itself is mode
0600. Use canonical firmware paths (normally `/usr/lib/firmware/...` on merged
`/usr` installations). Source/helper files and private input copies must be
staged by the operator; the supervisor does not copy, publish or install them.
No example below is a functioning profile: every placeholder must be replaced
with qualified local facts and correct JSON integer values.

```json
{
  "schema": 1,
  "model": "SM-G965N",
  "expected_boot_sha256": "CURRENT_QUALIFIED_BOOT_SHA256",
  "kernel_receipt": {"path": "/var/lib/g965n-sensors/inputs/startup.json", "sha256": "SHA256"},
  "backup_manifest": {"path": "/var/lib/g965n-sensors/inputs/backup.json", "sha256": "SHA256"},
  "programs": {
    "supervisor": {"path": "/var/lib/g965n-sensors/sensor-runtime.py", "sha256": "SHA256"},
    "runtime": {"path": "/var/lib/g965n-sensors/vendor-runtime.py", "sha256": "SHA256"},
    "kernel_verifier": {"path": "/var/lib/g965n-sensors/deploy-drivers.py", "sha256": "SHA256"},
    "broker": {"path": "/var/lib/g965n-sensors/ssp-iio-broker.py", "sha256": "SHA256"},
    "ssp_probe": {"path": "/var/lib/g965n-sensors/ssp-probe.py", "sha256": "SHA256"}
  },
  "module": {"path": "/var/lib/g965n-sensors/zrn-bbd.ko", "sha256": "SHA256", "bytes": "ACTUAL_INTEGER"},
  "iio_bridge": {"path": "/var/lib/g965n-sensors/g965n-iio-bridge.ko", "sha256": "SHA256", "bytes": "ACTUAL_INTEGER", "device": "/dev/g965n-iio-bridge"},
  "hub_patch": {"path": "/usr/lib/firmware/g965n/bcm4773-patch.bin", "sha256": "SHA256"},
  "vendor": {"lhd_sha256": "SHA256", "config_sha256": "SHA256"},
  "identity": {"chip_id": "QUALIFIED_INTEGER", "firmware": "QUALIFIED_INTEGER", "sensor_mask": "QUALIFIED_INTEGER"},
  "accel": {"enabled": false},
  "timeouts": {"startup": 60, "cleanup": 25}
}
```

The original exact kernel receipt must explicitly qualify built-in IIO and
contain the matching transport module hash/byte size. Both `.ko` files must be
AArch64 ELF and match the exact release/SMP/preempt/module-unload/architecture
vermagic contract. Source code is pinned separately from private firmware;
never publish extracted lhd, hub patch, device profiles, receipts or logs.

ALS-only is the initial default: acceleration is explicitly false, no matrix
argument is passed, no orientation evidence is invented, the bridge receives
`enable_accel=0`, and the broker enables only sensor 9. READY requires an actual
ALS frame published through IIO.

Acceleration requires `accel.enabled=true`, `range_g=8`, a nine-integer signed
permutation `mount_matrix`, and a pinned `orientation_evidence` JSON whose
`status="verified"`, `geometry_validated=true`, model, range and matrix all
match. The bridge then receives `enable_accel=1` plus that exact comma-separated
matrix, and the broker requires real acceleration and ALS publication. Do not
infer mounting geometry from package registers, random motion or an invented
identity matrix.

## Broker launch interface

The supervisor runs only:

```text
/usr/bin/python3 PINNED_BROKER --profile PRIVATE_PROFILE --sensor-service-child --ready-fd N --stop-fd M
```

It passes `G965N_SENSOR_PROFILE_SHA256` in a minimal environment, not the user's
GPU/application environment. The broker independently verifies the root-only
profile/hash and all required dependencies, owns the canonical SSP lock for
its entire life, serializes every transaction, and writes `READY\n` only after
actual IIO publication. STOP-pipe EOF, `STOP\n` or SIGTERM must trigger bounded
sensor-disable cleanup; a failed cleanup exits nonzero. No other process may
read `/dev/zrn_ssp` while the broker owns it. Existing ad-hoc SSP commands should
fail on that lock rather than compete.

## Explicit operator staging and enabling

There is intentionally no installer/enable subcommand. The template
`scripts/g965n/units/g965n-sensors.service.in` is inert source. The operator must
first verify all nine backup images outside the device, stage root-owned
private inputs, populate/hash the profile, and obtain explicit install/enable
approval. No command in the test/build workflow installs the unit.

The read-only native preflight is:

```sh
sudo python3 /var/lib/g965n-sensors/sensor-runtime.py check \
  --profile /var/lib/g965n-sensors/profile.json \
  --profile-sha256 ACTUAL_PROFILE_SHA256 --model SM-G965N
```

After separate approval, render all `@SUPERVISOR@`, `@PROFILE@` and
`@PROFILE_SHA256@` fields to exact fixed private paths/hash, review the completed
unit, install it specifically as `/etc/systemd/system/g965n-sensors.service`,
and explicitly run `systemctl daemon-reload` and `systemctl enable --now g965n-sensors.service`. Those administrative actions are not performed by this
source helper. Do not use an arbitrary transient unit name: the supervisor
verifies its own unit MainPID/cgroup before modifying that unit's device policy.
The fixed ExecStart includes explicit model, backup-verification confirmation
and sensor-start consent; merely copying source cannot activate sensors.

A first install still requires hardware evidence for module identity reuse,
all runtime/device-policy restrictions, real ALS READY, consumer-visible IIO,
ordered stop, no residual child cgroup members, and clean startup/stop kernel
logs. A successful host test does not qualify boot startup or long-term support.

## Host checks

`python3 tests/test_sensor_runtime.py` uses mocked native/module/vendor APIs and
real local pipes/flocks. It checks ALS-only flags, guarded acceleration evidence,
fixed broker argv, exact READY acknowledgement, setup-only `m` permissions,
failed-node-creation revocation, lease downgrade exclusion,
no-truncation/no-symlink locks, sensor-only node selection, owner/cgroup guarded
cleanup, no unmount for shared runtime, and broker-before-lhd cleanup even when
a child times out. `tests/test_vendor_runtime_resume.py` retains all existing
modem provenance/migration semantics. None of these tests loads a module,
mounts a device, changes the live service or accesses firmware.

The per-path permission update used for the `rwm` → `rw` transition is supported
by [systemd v255's device-allow update implementation](https://github.com/systemd/systemd/blob/v255/src/core/cgroup.c#L726): an existing path's permissions are
replaced. A successful mock or source review is not proof that the live unit's
BPF/device policy has been applied; the native trial must verify that separately.

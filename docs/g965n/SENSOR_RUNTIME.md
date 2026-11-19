# Gated sensor-only runtime supervisor

Native#27 qualifies the reviewed acceleration/ALS profile, real IIO consumers,
ordered stop/restart and actual reboot auto-start on one G965N. The source
helper itself does not install or enable a service. It never starts CP/CBD/RIL, resumes modem state, mounts EFS,
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


## Native#27 results and remaining scope

Real exact-BOOT transport/bridge loading, phase-specific rwm→rw policy and
child privilege restrictions passed native startup. First startup uncovered a
transport-ready race; the broker now waits read-only/bounded before identity.
Live IIO files expose actual acceleration scale/mounting and processed lux.
Normal user-manager SensorProxy claims and Qt LightSensor readings work; an
SSH-session claim is denied by the normal active-session policy. That policy
was preserved. Only the parent retains NOTIFY_SOCKET for systemd readiness.

A source-pinned six-pose profile enabled acceleration; GNOME reported panel
orientation management and normal/left-up transforms0/1. Owner confirmed
landscape and touch, including after a real reboot. Ordered stop removed
IIO/children/mounts; restart and enabled-at-boot startup passed. No automatic
hardware restart is configured. Service failure invalidates/unregisters readings.
This runtime holds the canonical vendor-runtime lease: stop it before modem
maintenance/migration tools, and do not claim simultaneous modem integration.

ALS is available to standard consumers but the panel has no ported brightness
control; no automatic dimming claim follows. Magnetometer/heading, proximity,
pressure/temperature and gyro system consumers remain separate. The next
maintainer must preserve firmware privacy, per-BOOT package/backup/profile
pins and actual pose evidence rather than copying an unqualified identity
matrix. Long endurance and power are still unverified.

## Opt-in single standby attempt on startup

On the qualified native #44 transport module, set
`"single_boot_standby": true` inside the existing `transport` object.
The supervisor verifies the module supports the parameter before it
loads the pinned file. The module performs the first normal standby
attempt, then the usual firmware startup, live hub identity check
and sensor readiness checks determine whether the service can start.
If MCU_RESP stays high, the driver reports that the reset was
unconfirmed. Explicit recovery resets retain the original retry path.
An omitted or false setting uses the original startup policy.

## Opt-in pressure IIO on native #44

For the pinned LPS22H SSP configuration, set `"pressure": {"enabled": true}`
in the root-owned sensor profile. The supervisor passes `enable_pressure=1`
to the bridge, and the broker verifies the live SSP identity and advertised
ID 5 before adding it. Use the updated broker, supervisor, and bridge as a
matched set. Pin the rebuilt bridge to the matching BOOT in the module
receipt, then recompute the receipt, program, profile and unit pins with the
same procedures used for acceleration. A profile with no pressure policy keeps
the existing sensor selection.

Ordinary Linux clients can read `in_pressure_raw` and `in_pressure_scale` on
the IIO device named `g965n-ssp-pressure`. Their product is pressure in kPa.
The same device reports its die temperature through `in_temp_input` in
millicelsius when the frame includes a valid temperature. The unit follows
the pinned SSP factory formatting path and the chip's
[temperature specification](https://www.st.com/resource/en/datasheet/lps22hb.pdf).
Pressure-only frames continue to work and return `ENODATA` for temperature.
Pressure and temperature accuracy against references, and the stock
per-device pressure compensation, still need qualification. See the
[bridge documentation](../../experiments/iio-bridge/README.md).

## Opt-in proximity IIO on native #44

Set `"proximity": {"enabled": true}` in the root-owned sensor profile for
the pinned TMD4906 SSP configuration. Use the matched broker,
supervisor and bridge and update their receipt/profile/unit pins as
above. The broker requires live advertised ID 7 and waits for an actual
hardware sample. The existing hub sends subsequent updates when the
detection state changes.

The stock Ubuntu SensorProxy recognizes this IIO device. Its
`HasProximity` and `ProximityNear` properties are observable with
`monitor-sensor --proximity`. The interface represents the hub's
near/far decision. Apps claim the sensor and choose how to respond.

## Opt-in raw gyroscope on native #44

Set `"gyro": {"enabled": true}` in the root-owned sensor profile for
the pinned LSM6DSL SSP configuration. Use the matched broker,
supervisor and bridge and update their receipt/profile/unit pins as
above. The broker checks advertised ID 1 and forwards the signed
three-axis vector as received. Applications can read
`in_anglvel_{x,y,z}_raw` on `g965n-ssp-gyro`. Continuous samples
expire when they are older than two seconds.

This interface publishes unscaled hub data. An application requiring
radians per second, screen-relative angular velocity, or synchronized
high-rate sampling needs additional scale, mounting and buffering work.

## Opt-in board thermistors on native #44

Set `"thermistor": {"enabled": true}` in the root-owned profile for
the matching SM-G965N revision 26. Pin the updated broker, supervisor,
SSP probe and bridge. The broker checks the live hardware revision and
requires the hub to advertise thermistor ID 34. It polls the two direct
read-only ADC commands every five seconds once the normal streams are
ready. The public
[revision 26 device tree](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts)
provides the two calibration tables. Both matched the verified stock
board's tables.

Read `in_temp0_input` and `in_temp1_input` on `g965n-ssp-thermistor`.
The files report millicelsius. An out-of-table value or a failed read
skips the pair. The last valid pair expires after 12 seconds and
always requires a live broker. This interface provides observation
of the two thermistors. Charging and overheat policy have their own
qualification requirements.

## Native rotation lock

Use GNOME's existing **Auto Rotate** tile in the top-right quick settings.
Turning it off locks the current orientation; turning it on permits automatic
rotation. It uses the standard
`org.gnome.settings-daemon.peripherals.touchscreen orientation-lock` setting:
`true` means locked, so the tile's enabled state is the inverse of that value.
The tile is conditional on Mutter managing panel orientation. With this port's
qualified acceleration feed, live `PanelOrientationManaged=true` was verified.
The owner initially missed the tile, then found it and confirmed that disabling
it prevents rotation. A subsequent read confirmed `orientation-lock=true` with
the sensor service still active. No extra toggle, Shell extension, policy
override or settings mutation was needed. A later real#28 reboot preserved orientation-lock=true; physical lock behavior
after that particular reboot was not separately repeated by the owner.


For the separate panel driver candidate and its limits, see
[PANEL_BRIGHTNESS.md](PANEL_BRIGHTNESS.md). For bounded raw magnetic capture
and private own-backup calibration preparation, see
[MAGNETIC_CALIBRATION.md](MAGNETIC_CALIBRATION.md). Native#28 real light-change
control and electrical-response evidence are recorded there; optical
luminance/color/flicker and compass heading quality remain unqualified.


## Experimental checked SSI acknowledgements

An optional `transport: {"strict_tx_ack": true}` policy requires the pinned
module's real ELF modinfo to advertise that parameter. Default is false.
For capable modules both requested arguments and loaded-module parameter
checks explicitly pinN/Y; merely omitting the policy cannot adopt an enabled
trial. Old modules without the capability remain compatible with default
profiles and refuse strict activation before hardware access.

The C candidate commits only positively acknowledged ring bytes, rejects
oversized ACKs and exhausted retries, and invalidates readiness/stops the
failed stream without kernel replay or reset in that TX-error path. A new
exclusive LHD open explicitly starts a new stream. Bootstrap and streaming
protocol semantics are not yet hardware-qualified. Do not enable this option
as an alleged fix merely because host tests or module compilation pass.

For a checked-ACK investigation, set `tx_ack_diagnostics` to `true` in
the same transport policy. The pinned module must advertise this
capability. The option defaults to false and logs rate-limited
transaction metadata for short acknowledgments, including prior and
returned receive credit. It leaves frame contents out of the log
and does not change how the transport retries or commits bytes.


Before an unattended strict-ACK boot trial, preserve a known workingNprofile
and its matching unit as root-only snapshots, pin both and exactBOOT/kernel
in a private rollback state, and review the inert rollback templates. Enable
the90s-onboot timer WITHOUT `--now` immediately before the authorized reboot:
starting it in an already-old boot would fire immediately. The restore helper
requires explicit model/backup/consent flags, validates before any stop/write,
atomically restores only the fixed sensor profile/unit/hash paths, disables
its one-shot timer and reboots when explicitly requested. A failed stop only
permits staging baseline when reboot was explicitly selected. Cancel/disable
the timer after a successful trial or observe recovery completely before
claiming anything. No script/build automatically arms this mechanism.

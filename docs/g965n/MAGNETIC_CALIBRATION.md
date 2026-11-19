# Magnetic calibration trial

Real SSP calibrated ID4 responds to movement. This alone does not qualify a
compass. The first four physical cardinal tests on#27 had status1,overflow0,
and a tentative planar calculation was up to36.8degrees from the owner's
reference. Do not install that calculation as a working heading backend.

The standard accel/ALS broker optionally supports a bounded private capture:

```json
"magnetic_capture": {
  "output": "/var/lib/g965n-sensors/magnetic-trials/UNIQUE.jsonl",
  "seconds": 120
}
```

Use a root-owned0700 parent and a new filename. The normal profile remains
unchanged. It enables only calibrated ID4 alongside qualified accel/ALS,
records separate real received batches with host monotonic receive time,
and removes ID4 after the bound. It never invents simultaneous timestamps,
zero samples or angles. The file is exclusive0600 and bounded to600s/2MiB.
Do not reboot with a one-shot capture profile still selected: an existing
output deliberately fails rather than overwriting evidence. Restore the
production profile/unit first, stop in the normal owned-cleanup order and
recompute all profile/unit hashes. Never unlink shared transport leases.

## Own backup input preparation

Run offline, with verified original stock BOOT and a current own EFS backup,
each beside its complete G965N backup manifest:

```sh
python3 experiments/sensors/prepare-magnetic-calibration.py \
  --stock-boot /PRIVATE/STOCK/BOOT.img \
  --efs-backup /PRIVATE/BACKUP/EFS.img \
  --docker-image s9-g965n-builder:24.04.3 \
  --output /PRIVATE/NEW-magnetic-init.json
```

On Linux with debugfs installed, omit `--docker-image`. The command verifies
model/hash/size, selects revision26's real stock board PDC, and reads only the
existing25byte `FactoryApp/gyro_cal_data`:12gyro bytes then13AKM state bytes.
It does not mount or write original EFS, create an absent calibration record,
fill missing data with zeros or access a handset. Output is private0600 and
must never enter Git, logs, releases or CI artifacts.

For an explicit trial only, stage it under the trusted private root tree and
add a `magnetic_initialization` pinned entry with absolute `path`, actual
`sha256` and integer `bytes`, alongside `magnetic_capture`. The supervisor and
broker validate the entry before enabling sensors. Stock protocol facts are
from Samsung's GPLv2 `factory/magnetic_common.c`, `ssp_dev.c` and `ssp.h` at
LineageOS exynos9810 commit6a9461f9460ca51d1217e5069a5d5556fcc79e63.

The trial reads factory fuse01, requires a valid reply, then sends volatile
FD/PDC and46/own magnetic state. It does **not** send F1 position, because F1
would also alter acceleration and invalidate its separately qualified matrix.
It never saves NVM or writes original identity partitions. A handshake or
status3 is not proof of correct magnetic orientation, absolute accuracy or
tilt compensation. A partially failed initialization stops the runtime;
there is no automatic reset/retry/zero-calibration fallback. Requalify against
independent headings and tilted poses before publishing any heading backend.

## Offline heading diagnostic

`experiments/sensors/heading-math.py` implements original vector geometry for
tilt-compensated **magnetic** heading. It is an offline diagnostic, never a
system backend or installer. Supply separate explicit accel and magnetic
mount matrices; the qualified acceleration matrix does not qualify the
magnetic one. It rejects poor calibration, overflow, acceleration far from
gravity, an indeterminate horizontal field, nearly vertical phone-top and
receive batches over250ms apart. Host receive association is not hardware
timestamp synchronization. Four math/failure regressions pass; they do not
establish handset accuracy.

On the actual old north capture its normal quality gate accepted no batch
(59low-quality,1missing nearby accel). The explicit low-accuracy diagnostic
option produced approximate N15.89/E91.72/S182.09/W307.53degrees using an
unqualified shared-axis candidate. All results remain `heading_qualified=false`.
The reference app's magnetic/true-north setting and declination were not
controlled, so this comparison is not an absolute heading calibration.

After private own-init,280actual records reported status3/overflow0. New
cardinal and tilted reference measurements are still required. Do not use the
old quality1 captures to certify the changed initialization, and do not fit
away their errors merely to reproduce four operator labels. The installed
Compass frontend still waits for a genuinely qualified backend.

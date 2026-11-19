# Experimental G965N SSP to IIO bridge

New GPL-2.0-only source. This is not a sensor simulator or a replacement sensor
hub driver. A separately verified root broker must supply **actual SSP data**
through the existing transport. The module does not access the hub, firmware,
protected partitions or networks, and never invents a measurement. It exposes
two genuine IIO devices through the standard kernel subsystem, without fake
sysfs files or a replacement D-Bus service.

This source has host validation only. It has not been built against or loaded
on the handset. A successful host test is not a successful device boot or
sensor reading. Root project orchestration owns kernel configuration, exact
BOOT/model/backup verification, deployment and recording hardware evidence.
Nothing here automatically loads the module or changes startup services.

## Kernel and ownership

The pinned Linux7.1 API requires `CONFIG_IIO`; current native kernel25 does not
provide that core. A new reviewed kernel must supply it before this module can
be used. `Makefile` is an ordinary external module build definition only:

```sh
make -C /absolute/kernel/source O=/absolute/kernel/output \
  ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  M=/absolute/project/experiments/iio-bridge modules
```

No build command flashes, loads modules or activates devices. Loading requires
`enable_g965n=1`, board compatibility `samsung,star2lte` and SoC compatibility
`samsung,exynos9810`. Acceleration is **disabled by default**:
`enable_accel=0` supports ALS only, requires no mount matrix, rejects every
acceleration frame with `EACCES`, and never registers an acceleration device.
Only `enable_accel=1` requires an explicit nine-entry `accel_mount_matrix` module
parameter. Physical axis evidence is not currently available, so initial
hardware qualification must remain ALS-only; do not guess a matrix. Every row and column must contain exactly one signed1; all other
entries are0. The code accepts rotations/reflections but does not claim a
particular physical orientation is correct. The owner must establish the
matrix and whether broker values have already been transformed. There is no
default identity matrix silently substituted for missing evidence.

The misc node `/dev/g965n-iio-bridge` is root-owned mode0600. Opening and writing
require `CAP_SYS_ADMIN`; the sole writer opens `O_WRONLY`. A second open fails
with `EBUSY`. Do not grant the node to an input group or ordinary applications.
The file uses the pinned kernel's `stream_open()` semantics: seeking,
positional I/O and atomic file positions are disabled, `FMODE_STREAM` is set,
and `.llseek` is NULL. Packet framing is enforced independently by the write
callback. The file's module reference prevents normal unload while a writer is open.

## Fixed packet contract

`g965n-iio-uapi.h` is the broker contract. One write must contain exactly one
48-byte little-endian frame, equivalent to Python `struct.pack('<IIQII3i3I',
...)`. Partial writes and batches are rejected, not silently accumulated.

| Field | Contract |
| --- | --- |
| version / size | 1 / 48 |
| seq | First accepted frame1, then strictly increasing unsigned64; no wrap |
| type | 1 acceleration, 2 illuminance, 3 heartbeat |
| flags | Acceleration exactly1, otherwise0 |
| value[3] | Signed32 encoding, constrained by sensor type |
| reserved[3] | All zero |

Acceleration values are signed16-bit SSP counts. Flag1 asserts the broker
**actually checked range8** through the validated SSP range query, rather than
assuming it. Only with explicit `enable_accel=1` and the verified physical matrix can raw
samples be advertised with
`in_accel_scale=0.002394202` m/s²/count (`IIO_VAL_INT_PLUS_NANO`). Every submitted
acceleration frame requires that flag. A broker losing the verified range
contract must stop submitting acceleration; a heartbeat cannot make old
acceleration fresh.

Illuminance value0 is a nonnegative actual integer lux reading; values1/2 and
flags are0. Real darkness0 is valid; a failed measurement must never be
converted to0. Heartbeat has all values/flags0, carries no measurement, and only
proves that the broker session remains live. Invalid frames do not consume a
sequence or refresh freshness. Failed first IIO registration restores the
previous cache/sequence, allowing a valid frame to be retried.

## Real IIO semantics and freshness

No IIO device is registered until that sensor's first valid real frame. This
avoids iio-sensor-proxy caching a fallback acceleration scale before range8 is
verified. Registration exposes:

- `g965n-ssp-accel`: `in_accel_x_raw`, `in_accel_y_raw`, `in_accel_z_raw`, shared
  scale and standard `in_accel_mount_matrix` through `IIO_MOUNT_MATRIX`.
- `g965n-ssp-light`: processed `in_illuminance_input`, integer lux.

Before the first reading, cache reads return `ENODATA` rather than a fabricated
sample. Acceleration requires both its own sample age and broker heartbeat
age to be at most2seconds. A newer heartbeat does not revive an old acceleration
sample. On-change light readings remain valid while broker heartbeat is fresh;
the broker must monitor transport/daemon health, not blindly heartbeat through
lost hardware access. Future timestamps are invalid; timestamps are assigned
by kernel boottime when a frame is accepted, not supplied by userspace.

Closing the last writer file invalidates both caches, unregisters and frees
both IIO devices, and resets the session for the next exclusive writer.
Lifecycle operations serialize open/write/registration/close. Separate sample
locking protects reads and cache updates. Sample locking is released before
IIO/kernfs unregister, so an active `read_raw` cannot deadlock removal. There
are no trigger, buffer, proximity, compass, magnetometer or gyroscope claims.

## Standard Ubuntu integration

The [Ubuntu iio-sensor-proxy3.5 source](https://archive.ubuntu.com/ubuntu/pool/main/i/iio-sensor-proxy/iio-sensor-proxy_3.5.orig.tar.gz)
contains `data/80-iio-sensor-proxy.rules` matching the three acceleration raw
attributes and `in_illuminance_input`. Its ordinary polling drivers read these
attributes when clients claim the sensor; no custom trigger or replacement
D-Bus interface is needed. It reads the standard acceleration scale and mount
matrix. Do not create buffer scan-elements merely to imitate a buffered device.
No special udev rule is needed beyond the installed upstream sensor rules.

The proxy's polling path is suitable for screen orientation and ambient light,
not proof of high-rate motion capture. Its compass path expects a buffered
actual tilt-compensated magnetic-north heading; raw magnetometer data must not
be mislabeled as that heading. Proximity support additionally needs a real
measurement and validated threshold, and is outside this module's scope.

## Host evidence and limits

Run `python3 experiments/iio-bridge/test_bridge.py`. Both harnesses compile the
actual shared C validation/freshness logic and actual module callbacks with
AddressSanitizer/UndefinedBehaviorSanitizer. They cover framing, version,
reserved/flags/type/range/negative/sequence rejection, all48 signed permutation
matrices, malicious matrix overflow input, initial/stale/disconnected ENODATA,
heartbeat-versus-on-change behavior, exclusive capability checks, default ALS-only without a matrix and disabled-acceleration
rejection, allocation/
registration failure cache rollback, lazy registration after real samples,
scale, and unregister callbacks simulating a concurrent kernfs reader without
holding the sample lock.

Host stubs do not prove Linux mutex scheduling, full IIO ABI registration,
module unload under real concurrency, physical mounting, range-query validity,
measured lux, or actual proxy/desktop integration. Those require the reviewed
new kernel, real broker and ordinary boot observations, recorded privately and
summarized honestly in the project changelog/validation matrix. Never publish
owner logs, identifiers, firmware or sensor recordings with this source.

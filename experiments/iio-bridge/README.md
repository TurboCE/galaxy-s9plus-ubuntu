# Experimental G965N SSP to IIO bridge

New GPL-2.0-only source. This is not a sensor simulator or a replacement sensor
hub driver. A separately verified root broker must supply **actual SSP data**
through the existing transport. The module does not access the hub, firmware,
protected partitions or networks, and never invents a measurement. It exposes
genuine IIO devices through the standard kernel subsystem, without fake
sysfs files or a replacement D-Bus service.

See the hardware checkpoints below for the features exercised on the handset.
Root project orchestration owns kernel configuration, exact
BOOT/model/backup verification, deployment and recording hardware evidence.
Nothing here automatically loads the module or changes startup services.

## Kernel and ownership

The pinned Linux 7.1 API requires `CONFIG_IIO` in the handset's target kernel.
`Makefile` is an ordinary external module build definition only:

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
parameter based on physical axis evidence for the device. Every row and column must contain exactly one signed1; all other
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
| type | 1 acceleration, 2 illuminance, 3 heartbeat, 4 pressure, 5 proximity, 6 gyroscope, 7 thermistor pair |
| flags | Acceleration exactly1. Pressure bit0 indicates its temperature field is present. Other sensors use0 |
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

Pressure is opt-in with `enable_pressure=1`. The broker takes the first
field of an actual SSP ID 5 sample from the pinned LPS22H configuration.
Frame value 0 contains positive raw counts within the signed 24-bit range.
When bit 0 is set, value 1 holds that sample's signed die temperature in
hundredths of a degree Celsius. A legacy pressure-only frame keeps the
other fields and flags at zero and leaves temperature unavailable. Based on the
[ST LPS22HB datasheet](https://www.st.com/resource/en/datasheet/lps22hb.pdf),
4096 counts/hPa becomes 1/40960 kPa per count for the
[Linux IIO ABI](https://www.kernel.org/doc/html/v5.16/admin-guide/abi-testing.html).
This interpretation follows the pinned Android sensor identity and parser,
the datasheet and the observed counts. Absolute accuracy and the optional
Android per-device compensation still require a reference measurement.

Proximity is opt-in with `enable_proximity=1`. The broker forwards the
actual TMD4906 SSP ID 7 detection bit. The bridge presents it as
unitless raw levels 0 (far) and 2 (near), with an integer near level of
1. This preserves the hub's own decision across the stock proxy's
integer threshold and hysteresis. The separate ADC field remains
available through the existing SSP diagnostic.

The gyroscope is opt-in with `enable_gyro=1`. The broker forwards all
three signed SSP ID 1 fields in hub axis order. The pinned Lineage IIO
path forwards those same fields. The
[LSM6DSL datasheet](https://www.st.com/resource/en/datasheet/lsm6dsl.pdf)
specifies sensitivity at the chip register for each full-scale setting.
The relationship between those register counts and the live hub output
and the mapping from hub to display axes still require verification.

The board thermistors are opt-in with `enable_thermistor=1`. The broker
converts the two direct ADC readings using the verified revision 26
tables and sends one pair in channel order. Only temperatures in the
table range `-20000..90000` millicelsius are accepted.

## Real IIO semantics and freshness

No IIO device is registered until that sensor's first valid real frame. This
avoids iio-sensor-proxy caching a fallback acceleration scale before range8 is
verified. Registration exposes:

- `g965n-ssp-accel`: `in_accel_x_raw`, `in_accel_y_raw`, `in_accel_z_raw`, shared
  scale and standard `in_accel_mount_matrix` through `IIO_MOUNT_MATRIX`.
- `g965n-ssp-light`: processed `in_illuminance_input`, integer lux.
- `g965n-ssp-pressure`: `in_pressure_raw` and `in_pressure_scale`, yielding kPa.
  `in_temp_input` reports the same chip's die temperature in millicelsius.
- `g965n-ssp-proximity`: `in_proximity_raw` and `in_proximity_nearlevel`.
- `g965n-ssp-gyro`: `in_anglvel_x_raw`, `in_anglvel_y_raw` and
  `in_anglvel_z_raw`, without a scale or mount matrix.
- `g965n-ssp-thermistor`: `in_temp0_input` and `in_temp1_input`, in
  millicelsius. The pair expires after 12 seconds even with current heartbeats.

Before the first reading, cache reads return `ENODATA` rather than a fabricated
sample. Acceleration, pressure and angular velocity each require both their own sample age and
broker heartbeat age to be at most two seconds. A newer heartbeat does not
revive an old sample. On-change light and proximity readings remain valid while broker heartbeat is fresh;
the broker must monitor transport/daemon health, not blindly heartbeat through
lost hardware access. Future timestamps are invalid; timestamps are assigned
by kernel boottime when a frame is accepted, not supplied by userspace.

Closing the last writer file invalidates the cache, unregisters and frees
the IIO devices, and resets the session for the next exclusive writer.
Lifecycle operations serialize open/write/registration/close. Separate sample
locking protects reads and cache updates. Sample locking is released before
IIO/kernfs unregister, so an active `read_raw` cannot deadlock removal. There
are no triggers or buffered motion capture. Compass and magnetometer
integration remain pending.

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
be mislabeled as that heading. Its proximity rule selects the stock poll driver
through `in_proximity_raw`, and that driver reads the bridge's
`in_proximity_nearlevel` when no device-specific udev override is set.
Run `monitor-sensor --proximity` to observe the published D-Bus state.

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


## Build and actual hardware checkpoint

Include `S9_EXPERIMENTAL_IIO_BRIDGE=1` with the existing AUDIO/BLUETOOTH/
SENSORS build flags when running `scripts/g965n/build.sh kernel`. This selects
IIO core and direct mode only and packages `iio-bridge/g965n-iio-bridge.ko` in
the exact BOOT receipt. Build never loads/flashes a device. Keep the guarded
BOOT-only install and fresh verified nine-partition backup workflow. A new
module package needs its own root-owned runtime profile, never an old module
with merely matching uname release.

Kernel#26 bridge compilation exposed removed no_llseek API and was not
installed. Corrected stream_open/nonseekable code built and booted as#27.
Native#27 real acceleration/light devices, stock SensorProxy, ordinary-user
Qt light readings, GNOME rotation/touch and reboot auto-start passed.
The default module remains ALS-only until explicit qualified acceleration
settings are supplied. Per-device six-pose evidence and hardware full-scale
verification remain mandatory; do not generalize one observed matrix to
unknown firmware/mounting configurations. See SENSOR_RUNTIME/VALIDATION docs.

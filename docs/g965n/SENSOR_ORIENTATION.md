# Evaluating a physical accelerometer mounting matrix

`scripts/g965n/sensor-orientation.py` evaluates private measurements and prints
an **unapplied** signed-permutation IIO matrix. It never reads a device, starts a
hub, writes a profile, alters udev, or enables automatic screen rotation.
Missing/ambiguous reference data fails with exit status2. Geometry validation
cannot authenticate physical labels or sample provenance; an operator must
independently validate those before installing any matrix.

## Source and ABI basis

Pinned Lineage Exynos9810 commit
`6a9461f9460ca51d1217e5069a5d5556fcc79e63`,
`drivers/sensorhub/brcm/factory/accel_lsm6dsl.c`, defines the active 8g
calibration's `MAX_ACCEL_1G` as 8192/2=4096 and uses it when removing gravity from
Z calibration. The 4g block is disabled with `#if 0`. `ssp_i2c.c:get_accel_range`
reads command `0xE1`, one unsigned byte; factory `accel_scale_range_show` prints
that byte directly as `FULL_SCALE:<value>G`, so a valid current reply8 denotes
8G rather than an undocumented enum. Require that real range check, not just a
historical observation of approximately4096 counts at rest. The corresponding
IIO scale is 9.80665/4096 m/s² per count.

Stock DT position7 is sent to firmware in commandF1; the pinned GPL host code
does not specify its transformation matrix. Do not turn position7 directly
into a guessed IIO mounting matrix or apply a firmware transform twice.

Ubuntu iio-sensor-proxy3.5 accepts a row-major matrix as semicolon-separated rows
and comma-separated elements, via `ACCEL_MOUNT_MATRIX` or standard sysfs mount
matrix attributes. Its orientation convention maps top-up to negativeY,
bottom-up to positiveY, phone top leaning toward the user's right (left edge
up) to positiveX, and the opposite to negativeX. Its source was inspected from
Ubuntu's official `iio-sensor-proxy_3.5.orig.tar.gz`, SHA256
`8689425f2287626a95d95b1e1e5b62e497d09dd08cf411084ed22166d4a49da5`
(67596 bytes), matching `iio-sensor-proxy_3.5-1build2.dsc`. These are interface
facts only: this utility independently implements vector/median mathematics;
it contains no GPL-3.0 proxy algorithm code.

## Required private input

Provide an object with `reference` and `poses`. `reference` must contain:

- `range_g`:8 and `range_verified`:true, supported by the current E1 reply.
- `sensor_frame_handedness`:"right" and a nonempty `frame_basis` explaining the
  independently established source-frame handedness.
- `z_positive_pose`:"face-up" or "face-down", and a nonempty `z_basis` stating
  the independently verified physical +Z convention. Merely choosing whichever
  makes the calculation pass is not evidence.

`poses` must map each of `top-up`, `top-right`, `top-left`, `bottom-up`,
`face-up`, `face-down` to arrays of contemporaneous `[rawX,rawY,rawZ]` samples.
The four edge poses mean the screen plane is vertical, not lying flat
on a table. `top-up` and `bottom-up` mean the phone top or bottom points upward,
respectively. `top-right` means the phone's top points right and its left edge
points upward. Face poses supply the separate Z check; edge poses alone cannot
qualify Z. Stop motion before capturing each window. Never combine observations
from different hub orientation settings, scales, kernels or physical devices.
Store input and results outside tracked files; only synthetic tests belong in
Git.

Example invocation (the input path is private, not a committed example):

```sh
python3 scripts/g965n/sensor-orientation.py /private/path/observations.json
```

Default minimum is12 stable frames per pose; `--minimum-frames` may increase it
but never lower it below8. The independent conservative acceptance checks are:
finite signed16 values, every frame magnitude within15% of4096, every frame
within0.08g of the pose median, dominant median axis at least0.9g and other axes
at most0.2g, opposite-pose residual at most0.12g, three independent axes and
pairwise normalized dot products at most0.15. These are qualification policy,
not claimed sensor noise specifications. The signed-permutation determinant
must be+1: reflections fail instead of silently flipping Z. Non-axis-aligned
physical mounting is deliberately unsupported and must not be approximated by
loosening thresholds.

Output `geometry_validated:true` means the supplied references and observations
passed those checks. `installed:false` is always present. Physical correctness,
Linux service discovery and actual portrait/landscape behavior still require
separate validation after the main operator reviews the candidate. Unqualified
input produces no profile, and this tool offers no apply/install mode.

## Explicit handheld 15-degree capture mode

`--handheld-15deg` enables a separate capture policy for a phone held with a
small common forward/backward tilt. The default strict policy above is
unchanged. This mode assigns discrete axes only; it does not estimate a precise
calibration rotation, remove sensor bias, or transform raw acceleration values.

For each median, the angle between its dominant signed axis and its full vector
must be at most15°, with dominant magnitude at least0.9g. The original minimum
frame count, finite/signed16 checks, frame-to-median stability0.08g, per-frame
magnitude0.85–1.15g, explicit verified8G range and right-handed/+Z reference
requirements remain. Full six-pose input remains mandatory.

Each opposite pair must have the same dominant axis, opposite dominant signs,
and normalized dot product at most `-cos(30°)` (at least150° opposition). With
positive and negative medians `p,n`, compute `d=(p-n)/2` and `c=(p+n)/2`.
This cancels equal posture tilt in that pair without asserting it is an actual
sensor offset. Require d magnitude0.85–1.15g and dominant-axis fit at most15°;
c's dominant component must be at most0.15g, and its off-axis vector magnitude
at most `sin(15°)*g`. The three pair-difference dominant axes must be distinct.
The output remains a signed-permutation matrix with determinant+1, never an
arbitrary fitted rotation. The strict mode's raw cross-pose dot-product check
is deliberately replaced by these explicitly bounded paired/discrete checks;
common tilt need not make raw median vectors perfectly orthogonal.

Output includes `capture_mode`, per-pose `capture_tilt_degrees`, paired fit and
common-component diagnostics, and `qualification:"discrete axis assignment
only"`. Similar gravity from yaw-only turning fails opposite-sign/pair tests;
ambiguous axes, too much tilt or inconsistent pairs fail instead of generating
a best-effort matrix. Consistently incorrect physical pose labels cannot be
proved false by geometry alone: operator verification of labels and reference
provenance remains necessary. No measured handset input is stored in this
repository; accepted/rejected regression fixtures are entirely synthetic.


## Repeating the actual capture

`experiments/sensors/capture-pose.py` records the same bounded eight-second,
last20-real-sample window used during qualification. It requires the already
verified native transport/own lhd runtime, actual8G range and canonical sole-
reader lock. Do not run it alongside the production broker: stop that service
and prepare the isolated manual runtime first. It labels but does not infer
physical posture, refuses overwriting private output, and sends matching
200ms add/remove payloads. No calibration/matrix/threshold write is made.

With a root-only output directory and the phone already held in the requested
pose, run on the handset from the sensor source directory:

```sh
python3 capture-pose.py --model SM-G965N --pose top-up --output /private/poses/top-up.json
```

Identity settling plus capture takes roughly15s; keep the pose until completion.
Repeat with new output paths for all six labels. For photo-landscape poses,
rotate within the screen plane while keeping the screen toward the observer;
yawing left/right with the phone top still pointing up does not provide an
independent gravity axis. Review unstable captures and explicitly recapture;
never replace them with generated/reference vectors. Combine only `frames`
from one unchanged hardware/range/firmware session into the private observations
object above, preserving all raw files. Native#25 qualification used the
explicit handheld15deg mode and source-pinned reference; native#27 later
verified actual normal/landscape desktop orientation and touch.

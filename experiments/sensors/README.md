# G965N BCM4773 sensor-hub transport

GPL-2.0 Broadcom transport and explicitly licensed board/compatibility sources
are pinned in SOURCES.json. Original copyright and licence notices remain.
The stock G965N tree confirms BCM4773 on SPI 0x13ac0000, gpa1-7 host request,
gph0-5 MCU request, gph0-4 MCU response and gph0-0..3 SPI pins. Sensors depend on
this hub and a vendor daemon; enabling IIO alone cannot make them work.

Changes made here:

- Require star2lte and explicit enable_g965n=1 before hardware access.
- Remove all embedded patch includes; request g965n/bcm4773-patch.bin locally
  before changing power/GPIO. No firmware bytes or firmware headers in Git.
- Bound reads against the runtime firmware size, with negative-offset checks.
- Propagate BBD node-init failures; refuse an unbound SPI device and guard
  partial teardown of unregistered driver/misc devices.
- Initialize work before error cleanup can cancel it.

Build with S9_EXPERIMENTAL_SENSORS=1; full module linking passed. To obtain the
patch from your own original BOOT backup, run extract-hub-patch.py STOCK_BOOT
OUTPUT. This handset's record passed format/payload-length checks and matched
the reference Android10 patch. Keep the output private and install locally at
/lib/firmware/g965n/bcm4773-patch.bin. The original C-string terminator is kept.

Manual load on kernel #6 created the transport devices. The owner's lhd ran in
the restricted vendor runtime and reached hub-ready when given its actual stock
/vendor/etc/sensor/lhd.conf argument. Fixed the POSIX write count and a1022-byte
payload bound (oversized writes were previously accepted into a smaller buffer).
ssp-probe.py read chip0x55/firmware21031900 and19 accel/18 gyro raw samples.
Zero-size and oversized-write guards were verified on the handset. This is not
end-to-end support: coordinate transforms, calibration, Linux integration and
restart/power behavior still need validation. Bounded test-service timeouts
intentionally stop the hub; do not label their teardown notices spontaneous crashes.
Do not automatically load this transport or start the closed daemon at boot.


## Bounded sensor selection

`ssp-probe.py --sensors` keeps `motion` (0/1), `light` (9), and `all`
(0/1/9) unchanged. Explicit additional groups are `compass` (4 only),
`pressure` (5), `proximity` (7), and `proximity-raw` (10). Every selected
sensor must be advertised by the actual hub before any enable/AP-state command.
These decoders target the pinned star2lte configuration only: magnetic overflow
is enabled, proximity is TMD4906, and pressure is LPS22H. They are not generic
SSP-layout autodetection. Each bypass record includes its original eight-byte
hub timestamp; the probe advances over it but does not establish physical
freshness or sampling rate. Startup, post-enable, and measurement-window counts
remain separate; every enabled ID receives bounded cleanup.

Wire tuples (little-endian, raw values; no physical-unit assertion):

| ID | Tuple | Bytes |
| --- | --- | --- |
| 2 | uncalibrated magnetic XYZ, offset XYZ: six signed16; overflow unsigned8 | 13 |
| 3 | raw magnetic XYZ: three signed16 | 6 |
| 4 | calibrated magnetic XYZ: three signed16; accuracy, overflow unsigned8 | 8 |
| 5 | pressure signed32, temperature signed16 | 6 |
| 7 | proximity detect unsigned8, ADC unsigned16 | 3 |
| 10 | proximity raw ADC unsigned16 | 2 |

Protocol facts are from LineageOS commit
`6a9461f9460ca51d1217e5069a5d5556fcc79e63`,
`drivers/sensorhub/brcm/{ssp.h,ssp_data.c,sensor_list.h}` and the star2lte
configuration. In particular the configured raw-proximity decoder consumes two
bytes despite the generic sensor-list report-size entry of one byte.
No calibration or coefficient writes are added. Android initializes magnetic
mounting/matrix/calibration, proximity thresholds and glass type separately;
receiving tuples alone does not qualify compass heading or near/far detection.
Pressure calibration is applied by Android's reporting path, so values here are
uncorrected. Ambient light zero without a measured cover/uncover response is
not a passing light-sensor result. The owner performs optical/motion checks
through the main operator; this helper does not start the vendor daemon.


For independent magnetic-path comparison use `magnetic-calibrated` (4 only),
`magnetic-uncalibrated` (2 only), or `magnetic-raw` (3 only). Optional
`--read-magnetic-fuse` reads command `0x01` as exactly three bytes, following
pinned `factory/magnetic_common.c:get_fuserom_data` (`AP2HUB_READ`). The separate
`valid_factory_bytes` flag follows that source's rejection of 0/255; it does
not establish heading accuracy. The command applies no matrix/calibration,
performs no self-test, and accesses no EFS. It requires the advertised magnetic
sensor bit. Read timeouts/length errors propagate without substituting zeros.


The ordinary `compass` check enables calibrated ID4 alone. Factory raw ID3 and
uncalibrated ID2 remain explicit diagnostics rather than simultaneous defaults.
On the handset, an isolated 40-second ID4 trial showed changing vectors and
accuracy reaching 2 without initialization/calibration writes. The preceding
simultaneous 2/3/4 trial had accuracy 0. Calibration settling versus influence
from factory-raw activation has not been separated experimentally; this is not
proof that simultaneous activation is prohibited by the protocol. Do not add
calibration writes merely to compensate for this difference. Pressure remains
raw; its temperature is hundredths of a degree Celsius according to pinned
`factory/pressure_lps22h.c:pressure_temperature_show`. The SSP source does not
establish pressure-to-hPa scaling, so the helper does not label raw pressure as
hPa.


Explicit `thermal` selects ID34: packed little-endian `u8` thermistor type and
`s16` raw ADC (3 bytes). Explicit `rotation` selects IDs16/17: four `s32`
quaternion components followed by `u8` accuracy (17 bytes each), exactly matching
`ssp.h:sensor_value` and `ssp_data.c:get_rot_sensordata`. Values are reported raw;
no thermistor-to-temperature conversion, quaternion normalization, orientation
frame, angle units, or Linux sensor-service integration is implied. The type
byte is necessary to distinguish thermistor channels. All existing groups keep
their selections. These explicit tests remain bounded and retain per-sensor
startup/window separation, advertised-mask checks, and disable cleanup.

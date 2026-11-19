# G965N advertised sensor inventory

This is a source inventory, not a hardware support declaration. A set bit in
`get_sensor_scanning_info` advertises a hub ID; it does not prove that a Linux
consumer exists, that samples are fresh, that calibration is correct, or that
an advertised feature works. In particular, placeholder/context IDs must not
be enabled just because their bits are set.

Source pin: LineageOS Exynos9810 commit
`6a9461f9460ca51d1217e5069a5d5556fcc79e63`,
`drivers/sensorhub/brcm/{sensor_list.h,ssp.h,ssp_data.c,ssp_input.c}`,
`factory/{magnetic_common.c,pressure_lps22h.c}`, and
`arch/arm64/configs/exynos9810-star2lte_defconfig`.
The upstream files retain Samsung Electronics copyright and GPL-2.0-or-later
notices; this independently written protocol inventory adds no vendor code or
firmware. Repository additions follow GPL-2.0-only terms.

The observed advertised IDs are
`0,1,2,3,4,5,7,9,10,12,13,14,15,16,17,18,24,25,26,27,28,29,30,31,32,33,34,35,36`.
Report modes below describe the pinned `SENSOR_INFO_*` declarations, not a
measured cadence. C=continuous, O=on change, S=special, U=unassigned/unknown in
the generic table. All numerical layouts are little-endian. Sizes exclude the
eight-byte SSP bypass timestamp. Physical/derived classifications describe
source intent; firmware algorithms and dependencies remain closed.

| ID | Exact enum name | Mode | Hub payload / source layout | Kind and qualification limit |
| --- | --- | --- | --- | --- |
| 0 | ACCELEROMETER_SENSOR | C | 6 B, `3 × s16` XYZ | Physical accelerometer, corrected path |
| 1 | GYROSCOPE_SENSOR | C | 12 B, `3 × s32` XYZ | Physical gyroscope, corrected path |
| 2 | GEOMAGNETIC_UNCALIB_SENSOR | C | 13 B, `6 × s16` XYZ/offset XYZ + `u8` overflow | Uncalibrated view of same magnetometer |
| 3 | GEOMAGNETIC_RAW | C | 6 B, `3 × s16` XYZ | Factory raw view; generic table disables normal reporting |
| 4 | GEOMAGNETIC_SENSOR | C | 8 B, `3 × s16` XYZ + `u8` accuracy + `u8` overflow | Calibrated view of same magnetometer; normal compass selection |
| 5 | PRESSURE_SENSOR | C | 6 B, `s32` pressure + `s16` temperature | Physical barometer; pressure calibration applied separately by Android |
| 7 | PROXIMITY_SENSOR | O | 3 B, `u8` detect + `u16` ADC | Physical proximity path with thresholds; not metric distance |
| 9 | LIGHT_SENSOR | O | 18 B, `u32` lux, `s32` CCT, `4 × u16` RGBW, `u8` time/gain | Physical ambient-light path plus computed lux/CCT |
| 10 | PROXIMITY_RAW | O | 2 B, `u16` ADC | Factory view of same proximity sensor; see size discrepancy below |
| 12 | ORIENTATION_SENSOR | U | No getter/report assignment or named SENSOR_INFO definition | Reserved/derived orientation ID; advertisement does not establish usable data contract |
| 13 | STEP_DETECTOR | O | 1 B, `u8` event | Derived motion event |
| 14 | SIG_MOTION_SENSOR | S | 1 B, `u8` event | Derived significant-motion event |
| 15 | GYRO_UNCALIB_SENSOR | C | 24 B, `6 × s32` XYZ/offset XYZ | Uncalibrated view of same gyro |
| 16 | GAME_ROTATION_VECTOR | C | 17 B, `4 × s32` quaternion + `u8` accuracy | Derived orientation/fusion; numerical quaternion scale not qualified here |
| 17 | ROTATION_VECTOR | C | 17 B, `4 × s32` quaternion + `u8` accuracy | Derived orientation/fusion; not proof of calibrated heading |
| 18 | STEP_COUNTER | O | 4 B, `u32` step difference | Derived; Android accumulates deltas, report size is not wire size |
| 24 | LIGHT_IR_SENSOR | O | 12 B, `5 × u16` IR/RGBW + `u8` time/gain | Additional optical view of light device; not a separate camera |
| 25 | INTERRUPT_GYRO_SENSOR | O | 12 B, `3 × s32` XYZ | Alternate interrupt gyro path, not another gyro |
| 26 | TILT_DETECTOR | O | 1 B, `u8` event | Derived motion event |
| 27 | PICKUP_GESTURE | C | 1 B, `u8` event | Derived motion event; source table says continuous despite gesture semantics |
| 28 | BULK_SENSOR | U | Getter/report explicitly NULL | Internal bulk/batching slot; no ordinary sample contract |
| 29 | GPS_SENSOR | U | Getter/report explicitly NULL | Internal GPS-labelled slot; not evidence that GNSS fix works |
| 30 | PROXIMITY_ALERT_SENSOR | O | 3 B, `u8` detect + `u16` ADC | Alternate proximity threshold/alert policy |
| 31 | LIGHT_FLICKER_SENSOR | O | 2 B, `s16` | Additional optical/firmware flicker result; units unqualified |
| 32 | LIGHT_CCT_SENSOR | O | Same 18 B layout as light ID9 | Additional light/CCT reporting path |
| 33 | ACCEL_UNCALIB_SENSOR | C | 12 B copied as opaque payload | Uncalibrated accelerometer path; getter only copies bytes, semantic field mapping not established here |
| 34 | THERMISTOR_SENSOR | S | 3 B, packed `u8` type + `s16` raw | Additional physical thermal measurement, requires device conversion tables |
| 35 | PROXIMITY_POCKET | C | 3 B, `u8` detect + `u16` ADC | Derived/context proximity-pocket path |
| 36 | WAKE_UP_MOTION | C | 1 B, `u8` event | Derived motion event; not evidence of Linux suspend/wake integration |

## Interpretation and boundaries

Most advertised IDs beyond the basic accelerometer, gyro, magnetometer,
barometer, proximity and ambient light expose alternative reporting paths,
factory data or derived algorithms rather than additional physical sensors.
Thermistor ID34 is an additional thermal measurement and must not be silently
classified as motion fusion. The independent SX9320 grip device is not proved
by this SSP mask (the pinned SSP SX9306 option is disabled). This inventory
makes no claim about cameras, fingerprint, heart-rate, NFC, GNSS, or other
hardware outside the qualified basic paths.

The TMD4906 configuration consumes **two** bytes for ID10 in
`get_proximity_rawdata`; the generic `SENSOR_INFO_PROXIMITY_RAW` entry says one.
The actual configured getter is authoritative for parsing. Likewise pressure
wire size is six, whereas its Android report is twelve after host expansion.
Magnetic overflow is enabled, giving 13/8-byte ID2/ID4 layouts rather than the
12/7-byte alternatives. Light report-lux is enabled and two-byte gain disabled,
giving the 18-byte layout. Mode O permits a post-enable sample followed by no
further samples while the sensed value is unchanged.

The owner-assisted basic-path trials supplied optical cover/uncover responses
for light/proximity and changing motion/magnetic vectors; pressure samples also
arrived. Those are the scope of the current evidence, not qualification of
every row above. Isolated ID4 reached accuracy 2 without initialization writes;
calibration settling versus simultaneous factory-raw influence remains
unresolved. The normal `compass` diagnostic therefore selects ID4 alone.
See the main validation matrix and CHANGELOG for exact trial results and
remaining integration gaps; do not promote the other rows to working based on
this source inventory. No new probes, sensor enables or device writes were
performed to create this document.

## Thermistor special events versus direct ADC reads

Pinned `factory/thermistor.c:initialize_thermistor_table` writes only two
threshold ADC values (upper/sub table index18) using command `0xB3`, four bytes;
it does not upload the entire conversion tables. The source's table index rule
is -20 + 5×index Celsius, making that index the 70°C threshold. The downstream
`ssp_iio.c:report_thermistor_data` converts event raw values through device tables
and sends a battery overheat notification. Thus ID34's special event path is
not evidence of a periodic thermometer stream. No samples in the bounded trial
without threshold initialization do not identify a format fault; that trial
remains unqualified.

A distinct source-defined read-only path exists: channel0 command `0xA9`, then
channel1 `0xAA`, each `AP2HUB_READ`, two-byte unsigned little-endian raw ADC.
`ssp-probe.py --read-thermal-adc` exposes this only after identity and ID34-mask
checks, without starting a bypass stream or writing thresholds/calibration.
Temperature conversion requires the correct device tables and remains separate.

For IDs16/17, the final byte is named `acc_rot` in the source but passed through
without interpretation. The observed value246 does not have a proven ordinary
accuracy-grade interpretation; quaternion scale and orientation conventions
also remain unqualified. Raw packet receipt alone is the current evidence.

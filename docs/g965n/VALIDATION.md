# SM-G965N hardware validation

Evidence date: 2026-11-19. One Korean SM-G965N rev26 / 256GB,
original firmware G965NKSU5FVA2. Target is parity with the hardware features
supported by the reference LineageOS build, not just desktop startup.
A build or a driver node is not sufficient evidence of a working function.

| Feature | Actual evidence | State |
|---|---|---|
| TWRP and recovery | 3.3.1-0 root; nine partitions backed up with device hash checks | Verified |
| Source build and installation | Own G965N firmware; rootfs and BOOT readback hashes passed | First installation verified |
| CPU / RAM | 8 online cores; 5523MiB usable RAM | Verified |
| Native builds / Git | Git clone+pull; real fixdep C source compiled on each CPU, 8 identical object hashes | Short test passed |
| Storage | USERDATA mounted as root and grew to 230GiB | Verified |
| Display / touch | Owner confirmed desktop/touch; 2x desktop scaling persisted at 720x1480 logical pixels | #14 touch binds after rail reset with no initial I2C timeout; basic interaction previously owner verified; apps wider than 720 minimum still need adaptations |
| GPU | #21 isolated patched Mesa with nocrc,noafbc: exact128x128 readback100, full33 positive scene rows, fullscreen1440x2960 U-tiled presentation and FIFO61/61/61fps;0 new matching GPU faults/timeouts; actual private-library maps verified | Bounded isolated rendering passed.100us IRQ generation-check rejections +1 with40ms completion wait failures0; frame impact unconfirmed. System desktop remains on the previously failing Mesa stack. Desktop/browser/endurance, CRC-enabled operation and allocation policy remain unqualified |
| Wi-Fi | Connected; HTTPS200 explicitly bound to Wi-Fi; NTP synchronized | Data path verified; long reconnect tests pending |
| Wi-Fi Direct / roaming | #21 P2P creation waits for IF_ADD and fails; roam-trigger firmware command rejected with collapsed error -52 | P2P not normal; roaming cause and actual handover unverified |
| USB networking / SSH | Mac received address automatically; key-only SSH works | Verified |
| Manual wired disconnect recovery | Console identified Wi-Fi path; privileged reconnection + gadget rebind restored USB SSH | Verified |
| System services | #14 no failed system units; SO_PASSSEC set/get=1, former errno95/boot messages resolved; missing Dbusmenu dependency/import messages resolved | Bounded observation; other clkout/MFD/Wi-Fi boot messages remain |
| LTE / voice / SMS | Private-copy RFS replies; active KT phone SIM; combined CS/PS profile; repeated CEREG0,1 | Historical home LTE/EPS registration verified; #19 cold-boot/security trial panicked before any PDP command. Modem default remains opt-in; cold bring-up, PDP/IP/Internet, voice and SMS pending |
| Speakers / microphone / headset | Owner heard speaker tones and short recorded playback; #11 MICBIAS1 readback8065 confirms bypass cleared; GNOME input/output nodes persist | Initial speech replay failed with robotic/crackling sound. ABOX timing rule removed repeated resyncs; subsequent cue-assisted10s spoken recording/replay confirmed clear without crackling by owner. Short acoustic and owner-confirmed voice recognition/response tests pass; long quality pending. Full audio quality, headset/call paths, multi-mic and processing parity unverified |
| Bluetooth | hci0 firmware loaded at 3Mbaud; discovery found 12 peer addresses; missing AES supplied and controller power cycle passed | Discovery verified; exact-BOOT startup and hci0 persisted on#13; pairing/audio pending |
| Accelerometer / gyroscope | Own SSP probe: chip0x55, firmware21031900; 19 accel and18 gyro samples with varying raw values | Raw readings verified; axes/calibration/automatic rotation and persistence pending |
| Compass / light / proximity / other hub sensors | #15 isolated hub advertises light9; lux18 format sample received, actual fresh count1 in60s, lux/RGBW0; physical illumination not confirmed | Optical response, IIO/automatic brightness and other individual sensors remain unverified |
| Korean text | Noto CJK/emoji installed; ko fallback selects KR; Pango Korean sample has 0 missing glyphs | Font coverage verified; live app refresh may be needed |
| Vibration / notification RGB | Source audit found missing DT/config connections and upstream object/mask/bias errors; reviewed source fixes pass host C tests only | Not enabled or hardware-qualified; PWM clocks/supply/current limits and stock behavior parity pending |
| Cameras / flash / hardware video codecs | No full pipeline tested | Pending port/validation |
| GPS / NFC / fingerprint / other Lineage-supported sensors | No end-to-end test yet | Pending port/validation |
| Buttons / brightness / USB OTG / fast charging | #16 non-root GPIO reader/seat ACL verified; #18 four direct DPMS cycles retained background heartbeats and fresh SSH,0 new matching display/GPU errors; original state restored | Screen-only software path verified; physical short/long button interaction, brightness, OTG and fast-charge negotiation pending |
| Charging / temperature / idle power | Native#16 input limit500000uA; inhibit → Not charging/N/A and near-zero battery current; auto → Charging/Fast restored | Charge-control field/encoding fixes hardware verified; no current increase. Fast charging negotiation, thermal endurance and screen-off drain unverified |
| Sleep / resume / warm reboot | Sleep masked; upstream warm-reboot/deep-idle issues unresolved | Not normal |

Software guard regressions cover recovery, transfers, filesystem status,
Wi-Fi recovery, ACPM dispatch, hub patch validation BOOT-only updates and private RFS copies.
CI never flashes or publishes blobs.
The full-function target is **not achieved**. Only the individual observations above are verified; full LTE/audio/Bluetooth/sensor support is not claimed.

GPU diagnosis: the preserved#21 timeout dump's valid fragment metadata shows
an actual1440x2896 AFBC32x8 render target, versus the reported1440x2960 window.
Its simple header/body extents fit the backing allocation. Earlier noafbc
environment-only comparisons did not verify the actual modifier, so they do
not exclude compression as a contributor. The invalid sparse-heap dump object
is not decoded or treated as valid evidence. No additional stress run or
physical light-response test is implied by this metadata inspection.
The source-only zero-initialization correction for invalid dump ranges is not
a GPU-stability fix or a claim that sparse heap capture is now supported.
The later#21 nocrc,noafbc protocol comparison still presents AFBC32x8 buffers
and incurs five glmark timeouts. Interleaved protocol output invalidated the
runner's unmodified scene-completeness check; it is a diagnostic comparison,
not another qualified rendering pass. All temporary session state was restored.
The isolated Mesa explicit-modifier candidate has passed host selector tests
and native configuration/compilation. Output hashes, coherent vendor paths and
ARM64 ELF headers verified. An isolated128x128/100-frame readback then passed
with zero pixel mismatches/new matching kernel faults and private-library load
proof. A later patched windowed native-request targeted run passed3/3 scenes
with0 new GPU faults/timeouts and actual U-tiled presentation/private-library
maps. Most windowed buffers were1440x2896. The desktop still uses system Mesa.

A separate isolated fullscreen targeted run now passes3/3 with all11772
committed buffers1440x2960/U-tiled and0 new GPU faults/timeouts. The later full33/FIFO suite also completes without new GPU journal faults,
with one internal100us IRQ-check rejection of undetermined frame impact.
Desktop and endurance qualification remain pending; system Mesa unchanged.

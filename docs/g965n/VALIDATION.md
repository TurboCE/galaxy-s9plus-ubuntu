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
| GPU | #14 same-kernel FIFO old31/31/31fps → latch60/61/61fps; #18 full33 +100 exact +FIFO61/61/61fps at512x512 pass,0 matching faults/new IRQ-check timeouts, runtime PM/DVFS retained | One-frame delay and repeated process polling reduced in bounded tests; generation-associated completion passed bounded hardware cadence test; #16 later idle vblank timeout prompted #18 tracked-tail/initial-enable fix; four bounded DPMS cycles/idle/SSH passed with0 new matching errors; owner reports improvement but residual desktop stutter;1440x2960 full33 stress FAILED with3 glmark scheduler timeouts despite FIFO61x3; #21 public targeted3-scene run stillFAILED with5 scheduler timeouts, all cores ready. nocrc remains required, lowmemY retained; private-high/shared-low allocation and long stability pending |
| Wi-Fi | Connected; HTTPS200 explicitly bound to Wi-Fi; NTP synchronized | Data path verified; long reconnect tests pending |
| USB networking / SSH | Mac received address automatically; key-only SSH works | Verified |
| Manual wired disconnect recovery | Console identified Wi-Fi path; privileged reconnection + gadget rebind restored USB SSH | Verified |
| System services | #14 no failed system units; SO_PASSSEC set/get=1, former errno95/boot messages resolved; missing Dbusmenu dependency/import messages resolved | Bounded observation; other clkout/MFD/Wi-Fi boot messages remain |
| LTE / voice / SMS | Private-copy RFS replies; active KT phone SIM; combined CS/PS profile; repeated CEREG0,1 | Historical home LTE/EPS registration verified; #19 cold-boot/security trial panicked before any PDP command. Modem default remains opt-in; cold bring-up, PDP/IP/Internet, voice and SMS pending |
| Speakers / microphone / headset | Owner heard speaker tones and short recorded playback; #11 MICBIAS1 readback8065 confirms bypass cleared; GNOME input/output nodes persist | Initial speech replay failed with robotic/crackling sound. ABOX timing rule removed repeated resyncs; subsequent cue-assisted10s spoken recording/replay confirmed clear without crackling by owner. Short acoustic and owner-confirmed voice recognition/response tests pass; long quality pending. Full audio quality, headset/call paths, multi-mic and processing parity unverified |
| Bluetooth | hci0 firmware loaded at 3Mbaud; discovery found 12 peer addresses; missing AES supplied and controller power cycle passed | Discovery verified; exact-BOOT startup and hci0 persisted on#13; pairing/audio pending |
| Accelerometer / gyroscope | Own SSP probe: chip0x55, firmware21031900; 19 accel and18 gyro samples with varying raw values | Raw readings verified; axes/calibration/automatic rotation and persistence pending |
| Compass / light / proximity / other hub sensors | #15 isolated hub advertises light9; lux18 format sample received, actual fresh count1 in60s, lux/RGBW0; physical illumination not confirmed | Optical response, IIO/automatic brightness and other individual sensors remain unverified |
| Korean text | Noto CJK/emoji installed; ko fallback selects KR; Pango Korean sample has 0 missing glyphs | Font coverage verified; live app refresh may be needed |
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

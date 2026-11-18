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
| Display / touch | Owner confirmed desktop/touch; 2x desktop scaling persisted at 720x1480 logical pixels | Basic interaction verified; apps wider than 720 minimum still need adaptations |
| GPU | #9/#11 AARCH64_4K: 768/1024MiB retained textures and exact readback pass with nocrc; #11 desktop also exposes DECON swiotlb failures with unrestricted allocations | CRC mitigation remains required. Kernel#12 boot defaultsY; owner reports black shapes gone; full33 scenes/readback pass with0 matching errors. Shared-display allocation repair and long stability pending; real compositor dispatch p95=34.74ms/max240.52ms confirms animation latency remains open; GPU-only pressure pass is not a desktop pass |
| Wi-Fi | Connected; HTTPS200 explicitly bound to Wi-Fi; NTP synchronized | Data path verified; long reconnect tests pending |
| USB networking / SSH | Mac received address automatically; key-only SSH works | Verified |
| Manual wired disconnect recovery | Console identified Wi-Fi path; privileged reconnection + gadget rebind restored USB SSH | Verified |
| System services | No failed system units during initial checks | Short observation only |
| LTE / voice / SMS | Private-copy RFS replies; active KT phone SIM; combined CS/PS profile; repeated CEREG0,1 | Home LTE/EPS registration verified; PDP/IP/Internet, voice and SMS pending |
| Speakers / microphone / headset | Owner heard speaker tones and short recorded playback; #11 MICBIAS1 readback8065 confirms bypass cleared; GNOME input/output nodes persist | Initial speech replay failed with robotic/crackling sound. ABOX timing rule removed repeated resyncs; subsequent cue-assisted10s spoken recording/replay confirmed clear without crackling by owner. Short acoustic and owner-confirmed voice recognition/response tests pass; long quality pending. Microphone quality, ASR, headset/call paths, multi-mic and processing parity unverified |
| Bluetooth | hci0 firmware loaded at 3Mbaud; discovery found 12 peer addresses; missing AES supplied and controller power cycle passed | Discovery verified; exact-BOOT startup persisted on#8; pairing/audio pending |
| Accelerometer / gyroscope | Own SSP probe: chip0x55, firmware21031900; 19 accel and18 gyro samples with varying raw values | Raw readings verified; axes/calibration/automatic rotation and persistence pending |
| Compass / light / proximity / other hub sensors | Hub enumerated a sensor mask; no individual sample validation yet | Not normal yet |
| Korean text | Noto CJK/emoji installed; ko fallback selects KR; Pango Korean sample has 0 missing glyphs | Font coverage verified; live app refresh may be needed |
| Cameras / flash / hardware video codecs | No full pipeline tested | Pending port/validation |
| GPS / NFC / fingerprint / other Lineage-supported sensors | No end-to-end test yet | Pending port/validation |
| Buttons / brightness / USB OTG / fast charging | Only individual parts observed; no complete acceptance test | Pending |
| Charging / temperature / idle power | Battery stayed present during bring-up; native power testing still needed | Partial observation |
| Sleep / resume / warm reboot | Sleep masked; upstream warm-reboot/deep-idle issues unresolved | Not normal |

Software guard regressions cover recovery, transfers, filesystem status,
Wi-Fi recovery, ACPM dispatch, hub patch validation BOOT-only updates and private RFS copies.
CI never flashes or publishes blobs.
The full-function target is **not achieved**. Only the individual observations above are verified; full LTE/audio/Bluetooth/sensor support is not claimed.

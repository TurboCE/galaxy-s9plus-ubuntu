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
| GPU | Mali-G72/Panfrost GLES3.1; offscreen 100 texture/shader frames, 6,553,600 exact bytes, no new kernel faults in that interval | Basic readback passed; earlier GNOME/nautilus/Xwayland job faults remain unresolved |
| Wi-Fi | Connected; HTTPS200 explicitly bound to Wi-Fi; NTP synchronized | Data path verified; long reconnect tests pending |
| USB networking / SSH | Mac received address automatically; key-only SSH works | Verified |
| Manual wired disconnect recovery | Console identified Wi-Fi path; privileged reconnection + gadget rebind restored USB SSH | Verified |
| System services | No failed system units during initial checks | Short observation only |
| LTE / voice / SMS | Private-copy RFS replies; active KT phone SIM; combined CS/PS profile; repeated CEREG0,1 | Home LTE/EPS registration verified; PDP/IP/Internet, voice and SMS pending |
| Speakers / microphone / headset | ABOX CRL0 booted; 2s silent PCM, 3s capture; two test frequencies observed in 5s capture; owner heard two quiet tones | Basic speaker/mic path passed; UCM exposes GNOME input/output; headset/call audio/quality and reboot persistence pending |
| Bluetooth | hci0 firmware loaded at 3Mbaud; discovery found 12 peer addresses; missing AES supplied and controller power cycle passed | Discovery verified; pairing, audio and reboot persistence pending |
| Accelerometer / gyroscope | Own SSP probe: chip0x55, firmware21031900; 19 accel and18 gyro samples with varying raw values | Raw readings verified; axes/calibration/automatic rotation and persistence pending |
| Compass / light / proximity / other hub sensors | Hub enumerated a sensor mask; no individual sample validation yet | Not normal yet |
| Korean text | Noto CJK/emoji installed; ko fallback selects KR; Pango Korean sample has 0 missing glyphs | Font coverage verified; live app refresh may be needed |
| Cameras / flash / hardware video codecs | No full pipeline tested | Pending port/validation |
| GPS / NFC / fingerprint / other Lineage-supported sensors | No end-to-end test yet | Pending port/validation |
| Buttons / brightness / USB OTG / fast charging | Only individual parts observed; no complete acceptance test | Pending |
| Charging / temperature / idle power | Battery stayed present during bring-up; native power testing still needed | Partial observation |
| Sleep / resume / warm reboot | Sleep masked; upstream warm-reboot/deep-idle issues unresolved | Not normal |

23 software guard regressions cover recovery, transfers, filesystem status,
Wi-Fi recovery, ACPM dispatch, hub patch validation BOOT-only updates and private RFS copies.
CI never flashes or publishes blobs.
The full-function target is **not achieved**. Only the individual observations above are verified; full LTE/audio/Bluetooth/sensor support is not claimed.

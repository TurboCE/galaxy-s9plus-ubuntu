# SM-G965N hardware validation

Evidence date: 2026-11-18. One Korean SM-G965N rev26 / 256GB,
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
| Display / touch | Owner confirmed desktop and touch interaction | Basic interaction verified |
| GPU | Mali-G72/Panfrost GLES3.1; offscreen 100 texture/shader frames, 6,553,600 exact bytes, no new kernel faults in that interval | Basic readback passed; earlier GNOME/nautilus/Xwayland job faults remain unresolved |
| Wi-Fi | Connected; HTTPS200 explicitly bound to Wi-Fi; NTP synchronized | Data path verified; long reconnect tests pending |
| USB networking / SSH | Mac received address automatically; key-only SSH works | Verified |
| Manual wired disconnect recovery | Console identified Wi-Fi path; privileged reconnection + gadget rebind restored USB SSH | Verified |
| System services | No failed system units during initial checks | Short observation only |
| LTE / voice / SMS | Owner inserted USIM; compile-stage modem .ko exists, hardware load blocked | Not working yet |
| Speakers / microphone / headset | Experimental ALSA kernel + .ko build passed; not loaded on handset | Not working yet |
| Bluetooth | Baseline has no controller; guarded GPL board glue and HCI-enabled kernel compile/link passed | Hardware bring-up pending; not working yet |
| Accelerometer / gyroscope / compass / light / proximity | Baseline has no nodes; hub transport linked; own stock hub patch extracted/validated | Not exposed; not working |
| Cameras / flash / hardware video codecs | No full pipeline tested | Pending port/validation |
| GPS / NFC / fingerprint / other Lineage-supported sensors | No end-to-end test yet | Pending port/validation |
| Buttons / brightness / USB OTG / fast charging | Only individual parts observed; no complete acceptance test | Pending |
| Charging / temperature / idle power | Battery stayed present during bring-up; native power testing still needed | Partial observation |
| Sleep / resume / warm reboot | Sleep masked; upstream warm-reboot/deep-idle issues unresolved | Not normal |

20 software guard regressions cover recovery, transfers, filesystem status,
Wi-Fi recovery, ACPM dispatch, hub patch validation and BOOT-only updates.
CI never flashes or publishes blobs.
The full-function target is **not achieved**. No LTE/audio/Bluetooth/sensor success is claimed.

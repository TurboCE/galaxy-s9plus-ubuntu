# G965N ABOX audio prototype — not hardware qualified

This isolated prototype references LineageOS's GPL Exynos9810 ABOX/machine driver
and the explicitly GPL-2.0 `audio/driver/snd-zrn-abox.c` in ztOS. SOURCE.json pins
the latter file, original hash and changes. Its parent repository's GPL-3.0 is
not used as blanket permission to copy unlabelled files into GPL-2.0-only code.

G965N stock recovery exposes CS47L93 (SPI), ABOX at 0x17c50000, audio IRQ/GIC,
MAX98512 speaker paths and umts modem devices. LineageOS machine driver:
https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/sound/soc/samsung/exynos9810_madera.c

The #6 experimental kernel booted on G965N and the module ran Calliope CRL0.
Short silent playback, microphone capture and two-tone correlation passed;
the owner heard both quiet tones. UCM now exposes speaker/microphone to GNOME.
This is basic path evidence, not full audio/speech/headset/call qualification.
Exact-BOOT guarded driver startup and GNOME devices persisted on#8/#9.
The owner reports speech is not recognized. Gain alone did not repair it;
regulated MICBIAS1 configuration is under test. Microphone speech is not qualified.

Object compilation and full module linking against the Linux 7.1 port passed
after enabling ALSA PCM and preparing module link scripts/symbols. The first
boot baseline has SOUND disabled; only the separate experimental kernel matches
this module. Use a kernel built with the explicit option below:

```bash
S9_EXPERIMENTAL_AUDIO=1 bash scripts/g965n/build.sh kernel
```

This enables ALSA/PCM and GPIO-I2C, builds the external module and packages a
separate kernel image. Nothing is flashed or auto-loaded. Own-device Calliope
firmware is required at runtime, extracted locally; no binary is redistributed.

Before any load, validate stock G965N amplifier GPIOs/address/gain, clock/power
sequence, DMA/shared-memory reservations and corresponding firmware. Start with
speaker playback at low volume, then capture separately. Hardware probing is
blocked unless both star2lte compatibility and enable_g965n=1 are present.
Modem voice shared memory defaults off (cp_vss=0), capture stays off, and the
amplifier defaults to its minimum digital setting. Use only the opt-in exact-BOOT guarded startup installer; arbitrary autoload is not qualified.

Do not enable microphone capture, call audio, speaker calibration or DSM until
their routes and firmware match. Preserve original EFS calibration; do not run
automated EFS writes. A successful C compile proves API compatibility only.

Extract firmware while still in TWRP: `python3 experiments/audio/extract.py --serial SERIAL`.
The extraction ran successfully on G965N and verified all three Calliope files.

## WirePlumber0.4 timing trial

On kernel#11 the owner reported robotic/crackling speech during replay. PipeWire
logged hundreds of repeated ABOX playback follower resyncs. With the explicit
ABOX-only properties in `device/base/etc/wireplumber/main.lua.d/51-g965n-audio-timing.lua`, the identical recording
became much clearer according to the owner, with occasional crackling still
reported. A bounded same-file replay produced no new PipeWire log entries.
This is a partial timing mitigation, not proof of full microphone/audio quality.
The individual effects of period size, headroom and non-mmap I/O were not isolated.

For the opt-in G965N audio prototype with WirePlumber0.4, copy this source file
to `/etc/wireplumber/main.lua.d/51-g965n-audio-timing.lua` after model/backup and
consent checks, then restart the desktop user's `wireplumber` service. Do not
install two copies of the rule. Remove the file and restart the same service to
roll back. WirePlumber0.5 uses a different configuration format: do not copy this
Lua file there. Reboot persistence and long concurrent recording/playback remain
pending. The image includes the ABOX-only rule; it takes effect only when the optional
audio prototype is active. This does not enable audio or load a module.
A subsequent cue-assisted10s spoken recording/replay passed the owner
intelligibility/no-crackling check. Long concurrent use still needs testing.

`python3 scripts/g965n/audio-record-play.py --record-play --seconds 10 --cue --start-delay 10` records short owner-authorized samples in
private runtime storage and replays original and normalized versions. Keep
recordings out of Git, obtain actual spoken-word feedback, and delete the
private files after the comparison. A nonzero signal is not a speech pass.

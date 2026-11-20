# Bounded standard feedback consumer

Project configuration/helpers: GPL-2.0-only. The installed Ubuntu feedbackd
0.2.1-1build2 package retains its own upstream license and source notices; no
upstream binary/source is redistributed here. Source review used the Ubuntu
[0.2.1 original archive](https://archive.ubuntu.com/ubuntu/pool/universe/f/feedbackd/feedbackd_0.2.1.orig.tar.xz).

The existing evdev rule alone did not connect this board to feedbackd. The new
rule matches **only** g965n-max77705-haptic and adds FEEDBACKD_TYPE=vibra.
The standalone theme contains only single100ms FF_RUMBLE events; full/quiet
use those same bounded events, silent has none, and no default theme is
inherited. No long/periodic effect or LED pattern is enabled. Rumble magnitude
is feedbackd's native32768, capped by the existing driver to32767 (normal PWM
duty below75%). Never install this consumer with the old idle-power driver.

## Required idle-power fix

A real fbcli trial with the former driver vibrated and stopped, but kept boost
and bias enabled while feedbackd held evdev open. Disabled the consumer before
changing the driver. `0006-g965n-haptic-idle-power.patch` moves MAX77705 supply/
bias activation from evdev open to actual playback, tears both down at stop,
clears firmware-retained motor/bias state before registration (probe fails on
write errors), cleans up enable errors, and cuts supply even when a PMIC motor-stop write
fails. Other PMIC variants retain their existing open/close policy.
The original source attribution and GPL notices remain unchanged.

`HAPTIC_IDLE_POWER.json` pins the0005 output, this additional patch and final
source. Build in a new directory using the normal recipe plus `--idle-power`:

```sh
python3 experiments/pmic/build-haptic-trial.py --idle-power \
  --kernel-source /path/to/qualified/source --kernel-out /path/to/qualified/out \
  --output /path/to/new-private-modules
python3 experiments/pmic/test_haptic_idle_power.py \
  --source /path/to/new-private-modules/g965n-haptic-trial.c
```

The builder never installs/flashes. It also builds the test program with
G965N_HAPTIC_IDLE_BOOST=0 to require rail-off *before* evdev close. Keep the
original build, installed module/test and both private pin manifests for rollback.
Review exact model/current BOOT/protected backup pins with haptic-control.py's
preflight and existing explicit consent before any installation. Stop feedbackd
before stopping/updating haptic modules; update only the reviewed module/test
and their private checksum manifests, then start/test the guarded driver.
Do not replace RECOVERY/EFS/CPEFS/RADIO or any bootloader.

## Configuration locations

After the driver test passes, install the Ubuntu feedbackd package, then these
new files without overwriting existing user configuration:

| Source | Destination |
|---|---|
| g965n.json | /usr/local/share/g965n-feedback/g965n.json |
| 71-g965n-feedback.rules | /etc/udev/rules.d/71-g965n-feedback.rules |
| g965n-feedbackd.service | selected user's .config/systemd/user/ |
| org.sigxcpu.Feedback.service | selected user's .local/share/dbus-1/services/ |

User files belong to the desktop user. Validate with `fbd-theme-validate`,
reload udev and trigger change only on the dedicated haptic event device,
reload the user manager, then enable/start g965n-feedbackd.service.
`fbcli --event=g965n-haptic-test --timeout=1` exercises the standard API.
Use an independent root rail-off fallback during first trials, as in the
existing guarded controller; a successful client return alone is insufficient.

Actual native48: three standard API trials observed boost/bias/MOTOR_EN1 during
playback and all0 afterward while the daemon still held the device open.
Guarded original100ms/8192 regression also passed with the updated idle-aware
test. Kernel serious patterns and failed units0. New module warm-boot persistence
has not yet been tested; a separate clean Mesa compilation is still running.
GNOME Shell does not automatically translate every notification into libfeedback
calls. No broad notification observer, keyboard hook or personal app setting is
installed. The standard service works for explicit libfeedback-aware callers;
GNOME-wide automatic notification feedback remains separate unfinished work.

Rollback: stop/disable the user feedback service and remove only these owned
D-Bus/udev overrides; restore the preserved old module/test and both pin files
with the guarded haptic service stopped, then restart/test the original driver.
Do not leave the persistent consumer running with the old open-powered driver.

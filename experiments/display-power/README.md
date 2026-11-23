# SM-G965N power key: panel off/on with background work retained

New code is GPL-2.0-only. The optional standard Linux uinput module preserves
its original GPL-2.0-or-later attribution/notices; no extracted firmware, modules,
backups, credentials or device identifiers are distributed. See UINPUT_REFERENCE.json.

GNOME on this handset advertises only nothing/suspend/hibernate/interactive for
power-button-action. The existing setting is nothing, preserving background
work. A manual Mutter panel write alone did not reset GNOME idle: pressing the
physical power key could briefly wake then blank again. Native ResetIdletime is
a test-only API here; its refusal was respected and no debug/unsafe mode enabled.

The root helper observes only the unique gpio-keys input device carrying
KEY_POWER, without an exclusive grab or reading a typing keyboard. It debounces
kernel monotonic timestamps and acts after release. It uses the pre-press panel
state to avoid toggling an already natively woken screen back off.

Off activates GNOME's normal screensaver/blank state and requests panel OFF.
On emits a single modifier-only local input pulse and lets GNOME wake normally. This
clears GNOME's actual idle state through its standard input path. A dedicated
uinput device advertises only Left Shift; it cannot type text or a password.
The exact-name udev rule marks this device as a keyboard/seat input. No suspend,
shutdown, lock-policy alteration or session-unlock call is used. Native lock
policy continues to apply. A changed native power-button policy is respected.

A model/current-BOOT/protected-backup guard runs before device setup. A native
ABI/module hash check gates loading the missing standard uinput backend. The
service has a30s watchdog. Closing the service destroys only its own virtual
input device; the shared Linux module can remain loaded. No arbitrary input or
remote-access endpoint is exposed by this helper.

## Build and install boundary

```sh
python3 experiments/display-power/build-uinput.py \
  --kernel-source /path/to/qualified/source \
  --kernel-out /path/to/qualified/output \
  --output /path/to/new/private/module-output
```

The builder checks exact source/header/ABI hashes, preserves upstream code and
never installs/loads/flashes. The actual module built with KCFLAGS=-Werror.
Deployment is separate: perform the handset guard, verify module hash/vermagic,
keep rollback copies and install power-key.py, misc/uinput.ko and pins.json
root-owned0600 under /usr/local/lib/g965n-display-power0700. Install the supplied
udev rule and unit0644, reload rules/systemd and enable/start g965n-power-key.
The helper's --check-only verifies the key/session/native interfaces without
creating a virtual input device or changing screen state.

Rollback: perform the same guard, disable/stop only this helper, remove its rule
and reload rules. Leave native power-button-action untouched. Remove uinput only
if a private current-boot receipt owns it and no other consumer is using it.
The physical key then returns to the original nothing behavior; Wi-Fi remote
screen control remains available.

## Hardware evidence

- Early direct-panel/pre-event fixes failed actual user tests (brief wake then
  blank). These failures are retained rather than labelled successful.
- Actual virtual input registration, keyboard tagging and idle timer change
  from about514s to0.5s were read back. No test-only idle API was enabled.
- Actual OFF held, then ON held for3s in a full software cycle.
- User subsequently confirmed physical key OFF/ON both normal.
- That short test was superseded by the user's longer-idle ON/OFF/ON flicker
  report. The new candidate removes the forced panel-ON write after native wake.
  `qualify-cycle.py` passed two90s OFF cycles: first light64/45ms, no subsequent
  DPMS/backlight drops during5s traces. The latest actual physical long-idle
  confirmation is pending because the user is unavailable; do not mark resolved.
- Autostart is enabled; actual reboot, locked-session behavior, very long holds,
  multiple GUI sessions and extended standby remain unqualified. Holding the
  physical buttons long enough for Samsung's hardware reset remains independent
  of this short-press helper. This is not suspend/power-off qualification.

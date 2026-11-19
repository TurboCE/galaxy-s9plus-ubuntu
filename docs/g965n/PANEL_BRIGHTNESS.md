# Inherited-panel brightness trial

The active display driver is `src/gpu/drm/s9p/s9p-decon.c`, which adopts
Samsung's running DECON/DSIM pipeline. Updating the otherwise unused mainline
S6E3HA8 panel driver would not add brightness to this port.

## Explicit build option

Add `S9_EXPERIMENTAL_PANEL_AOR=1` to the existing guarded experimental kernel
build recipe. It adds `s9p_decon.panel_aor=1` to the compiled command line.
Without this option, no backlight device is registered. Builds never flash.
Use the normal model/consent/fresh-nine-backup BOOT-only installer separately;
do not flash a generic S9 image or change the Samsung bootloader.

The candidate registers the standard raw backlight `g965n-panel-aor`, with
levels0..401 in the new smoothing candidate (the previously qualified kernel28..32 used0..16). Level0 sends display-off;1..401 select strictly decreasing stock
AOR dark-time values. These are discrete duty levels, not nits or a linear
luminance curve. Maximum selects stock AOR000c and preserves inherited gamma
and voltage commands. This is a limited duty-only implementation, **not** the
full Samsung MTP/gamma/temperature/ACL/HBM dimming stack. It does not implement
high brightness mode or claim calibrated color/luminance or flicker parity.

Register/value facts and the retained Samsung notice are in `panel-aor.h`.
The original GPLv2 sources are LineageOS
[`s6e3ha8_star2_a3_s0_panel.h`](https://github.com/LineageOS/android_kernel_samsung_exynos9810/blob/6a9461f9460ca51d1217e5069a5d5556fcc79e63/drivers/video/fbdev/exynos/panel/s6e3ha8/s6e3ha8_star2_a3_s0_panel.h)
and `dpu_9810/{dsim_drv.c,dsim_reg.c,regs-dsim.h}` at the same commit.
No extracted firmware, private MTP or owner calibration is published.

The packet writer accepts only reviewed1..3byte DCS writes, refuses inherited
packet-go batching, bounds FIFO waits, and always attempts vendor-key closure.
A bounded delayed worker slews output at most4 levels per40ms; a complete
1↔401 traversal takes about4seconds plus command/scheduler time. Pending targets
replace older ones, failures stop the worker, zero/off is immediate, and DPMS
down/device cleanup drains queued work. Wake restores the requested level
directly. Actual readback remains the last completed transaction, not the target.
These output transitions never filter or fabricate ALS samples.

One mutex serializes brightness with DPMS. It never sends brightness commands
while the panel is asleep; requested brightness is applied on wake. Successful
software readback means the bounded command transaction completed; it is not
an optical measurement of panel luminance. Errors invalidate cached readback.

## Qualification

Keep an independent timed restore to maximum before changing a live level;
preserve the previous BOOT and do not rely on a dark-screen UI to recover.
Check command errors, ordered level changes, zero/off and wake restoration,
then GNOME's standard brightness and ambient-light integration. Do not replace
that integration with a second competing brightness daemon.

Host C failure injection and kernel#28 build/native boot passed. A seven-step
16,12,8,4,1,0,16 sweep matched completed command readback. GNOME's normal
Brightness property was available; setting25percent produced raw4. Three
DPMS off/on cycles each read actual0 asleep and restored raw4 awake, with
sensor service active and no matching new panel/fatal/GPU errors. Real room-light ON/OFF subsequently drove standard GNOME backlight4→16→3.
A focused/fullscreen white-window16/1/16/1 comparison reproduced about0.32A
net battery-current change and voltage sag at maximum. This is physical
electrical-response evidence, not calibrated luminance/color/flicker or full
Samsung parity. A further real#28 reboot auto-started the updated sensor service and restored
brightness3/actual3 with ambient-enabled=true; audio/BT startup also passed.

`scripts/g965n/backlight-restore.py` saves a private exact-BOOT state. Stage
the script in a root-owned non-writable directory and save with explicit
model, actual BOOT hash/bytes, verified-backup confirmation and trial consent.
Arm an independent timer calling its restore action with the state's actual
hash **before** the manual sweep. `--keep-ambient-disabled` deliberately
prevents a recovery maximum from immediately being dimmed again. A successful
manual cleanup can restore the original ambient policy. The helper does not
create a unit or run a sweep automatically. Snapshot and command logs remain
private; no raw logs are needed in Git.

`scripts/g965n/observe-backlight.py` records only real ALS/backlight reads for
at most600seconds, in an exclusive0600 file. Missing/stale readings are not
reported as zero. Compare intervals with no manual brightness/DPMS writes:
actual0 with a nonzero request may mean the display is asleep. During a
bounded light-change test, use the normal desktop session's idle inhibitor,
then stop it afterwards. Do not globally disable idle or suspend policies.

GNOME46 uses the user's selected brightness as a relative ambient reference,
as shown by its [power-manager source](https://gitlab.gnome.org/GNOME/gnome-settings-daemon/-/blob/46.0/plugins/power/gsd-power-manager.c).
Starting at maximum in a3lux room can leave the result clamped at maximum;
that observation alone is not a failed ALS driver. Use the existing standard
brightness UI/API to choose a suitable reference, then validate a real light
change. Do not inject synthetic lux or add a competing brightness daemon.

The temporary `experiments/sensors/backlight-white-window.py` draws white
without changing settings, sensors or brightness and closes after75seconds.
Its state reports normal GTK focus/fullscreen, not optical measurements.
Do not infer panel power from net battery current alone; charger and system
load also contribute. The earlier locked-screen current trial was
inconclusive. In remote tests, merely setting Mutter PowerSave0 does not
reset a pre-existing idle state. Use normal session activity; do not enable
test-only idle-reset APIs or weaken GNOME unit/polkit restrictions.

## Native automatic-brightness control

Use Settings → Power → Power Saving → Automatic Screen Brightness. Native32
stock Control Center's visible switch was exercised through its normal toggle
action: ambient-enabled true→false→true. SensorProxy reports the real light
sensor. No duplicate brightness daemon or modified Settings application.

The401-level candidate uses unique duty values from the pinned Samsung PAC512
source, sorted for fixed inherited gamma. Original PAC order has gamma-boundary
reversals and must not be used unchanged in this limited duty-only driver.
No interpolation/new register range or voltage/gamma/HBM change. Host actualC
transaction/ramp/worker fault tests pass; native401 smoothness and DPMS results
must be recorded separately from the earlier16-level qualification above.
Rollback state pins exact BOOT and exact16or401 range; a range mismatch refuses
writes. Recovery waits up to6seconds for completed output rather than confusing
an accepted ramp target with applied brightness.

Native33 qualification:401→1/1→401 transitions took4.947/4.951seconds with100
monotonic observations (max4levels each). Owner confirmed actual automatic
brightness is sufficiently smooth. Standard GNOME25/75/14% off/on tests restored
raw103/302/60 within0.169/0.154/0.179s; zero and direct restore also passed.
Native ambient-enabled remainedtrue after cleanup. Earlier host-only candidate
statements are superseded by these bounded hardware and owner observations;
full optical/color/flicker/calibration qualification remains open.

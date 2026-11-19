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
levels0..16. Level0 sends display-off;1..16 select strictly decreasing stock
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

Host C failure injection passed and kernel#28 built. Native boot, DSIM
transactions, visible dimming and automatic brightness remain pending at this
source checkpoint; see CHANGELOG and the validation matrix for later evidence.

/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Limited duty-only dimming for the inherited star2_a3_s0 panel state.
 * AOR register/value facts: Samsung Electronics' GPLv2 S6E3HA8 driver,
 * Copyright (c) 2016 Samsung Electronics, LineageOS android_kernel_samsung_
 * exynos9810 6a9461f9460ca51d1217e5069a5d5556fcc79e63,
 * drivers/video/fbdev/exynos/panel/s6e3ha8/s6e3ha8_star2_a3_s0_panel.h.
 * This is NOT the stock gamma/MTP/temperature/HBM dimming implementation.
 * Keep inherited gamma and voltages; select only stock AOR values.
 */
#ifndef S9P_PANEL_AOR_H
#define S9P_PANEL_AOR_H

/* Increasing indices decrease dark time. No nits/linear-luminance claim. */
static const unsigned short s9p_aor_values[] = {
	0x0b72, 0x0b22, 0x0a90, 0x09ca,
	0x08c2, 0x0802, 0x06fe, 0x05e0,
	0x04a0, 0x0450, 0x03bd, 0x027e,
	0x01ca, 0x00e1, 0x007a, 0x000c,
};
#define S9P_AOR_MAX 16

/* Always attempt to close the vendor key, including a failed unlock/latch.
 * Transport errors must not be turned into successful brightness readback.
 * Caller serializes this entire transaction with every other panel command.
 */
static int s9p_aor_apply(void *context, unsigned int level,
		int (*send)(void *, const unsigned char *, unsigned int))
{
	const unsigned char unlock[] = {0xf0, 0x5a, 0x5a};
	const unsigned char lock[] = {0xf0, 0xa5, 0xa5};
	const unsigned char latch[] = {0xf7, 0x03};
	unsigned char duty[] = {0xb1, 0, 0};
	int ret, closed;

	if (!level || level > S9P_AOR_MAX)
		return -EINVAL;
	duty[1] = s9p_aor_values[level - 1] >> 8;
	duty[2] = s9p_aor_values[level - 1] & 0xff;
	ret = send(context, unlock, sizeof(unlock));
	if (!ret)
		ret = send(context, duty, sizeof(duty));
	if (!ret)
		ret = send(context, latch, sizeof(latch));
	closed = send(context, lock, sizeof(lock));
	return ret ? ret : closed;
}
#endif

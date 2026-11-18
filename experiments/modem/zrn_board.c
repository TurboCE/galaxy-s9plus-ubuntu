// SPDX-License-Identifier: GPL-2.0
/*
 * zrn-modem.ko: the three vendor drivers in it, registered in the order the
 * stock kernel brought them up (the mailbox, the shared memory, then the
 * modem interface that uses both). Each binds to its node of the device tree,
 * which the module adds itself: the stock tree's nodes, as an overlay
 * (zrn-modem-overlay.dts), so that the boot image stays as it is.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <linux/firmware.h>

static int overlay_id = -1;

extern struct platform_driver *zrn_mcu_ipc_driver, *zrn_shmem_driver, *zrn_modem_driver;
int zrn_shm_find_memory(void);

static struct platform_driver **drivers[] = {
	&zrn_mcu_ipc_driver, &zrn_shmem_driver, &zrn_modem_driver,
};

static bool enable_g965n;
module_param(enable_g965n, bool, 0444);

static int __init zrn_modem_init(void)
{
	int i, ret;
	const struct firmware *overlay;

	if (!of_machine_is_compatible("samsung,star2lte") || !enable_g965n)
		return -ENODEV;
	ret = zrn_shm_find_memory();
	if (ret)
		return ret;
	/* The local DTBO is generated from GPL board source and checked against
	 * the owner's stock BOOT. No opaque embedded overlay is used. */
	ret = request_firmware(&overlay, "g965n/modem.dtbo", NULL);
	if (ret)
		return ret;
	if (overlay->size < 40 || overlay->size > 128 * 1024) {
		release_firmware(overlay);
		return -EINVAL;
	}
	ret = of_overlay_fdt_apply(overlay->data, overlay->size, &overlay_id, NULL);
	release_firmware(overlay);
	if (ret) {
		pr_err("zrn-modem: device tree overlay: %d\n", ret);
		if (overlay_id >= 0)
			of_overlay_remove(&overlay_id);
		return ret;
	}
	for (i = 0; i < ARRAY_SIZE(drivers); i++) {
		ret = platform_driver_register(*drivers[i]);
		if (ret) {
			pr_err("zrn-modem: %s: %d\n", (*drivers[i])->driver.name, ret);
			while (--i >= 0)
				platform_driver_unregister(*drivers[i]);
			of_overlay_remove(&overlay_id);
			return ret;
		}
	}
	pr_info("zrn-modem: drivers registered\n");
	return 0;
}

static void __exit zrn_modem_exit(void)
{
	for (int i = ARRAY_SIZE(drivers) - 1; i >= 0; i--)
		platform_driver_unregister(*drivers[i]);
	if (overlay_id >= 0)
		of_overlay_remove(&overlay_id);
}

module_init(zrn_modem_init);
module_exit(zrn_modem_exit);
MODULE_DESCRIPTION("Samsung Shannon modem interface (exynos9810 vendor kernel) for mainline");
MODULE_LICENSE("GPL");

// SPDX-License-Identifier: GPL-2.0-only
/* Read only non-clearing status/configuration through the live owner's regmap.
 * Never read IRQ status, rebind the charger, change config or access raw I2C.
 */
#include <linux/device.h>
#include <linux/i2c.h>
#include <linux/mfd/max77705-private.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regmap.h>

static bool enable_g965n;
module_param(enable_g965n, bool, 0400);
static unsigned int int_ok, details0, details1, cnfg0, cnfg6, cnfg9;
module_param(int_ok, uint, 0400);
module_param(details0, uint, 0400);
module_param(details1, uint, 0400);
module_param(cnfg0, uint, 0400);
module_param(cnfg6, uint, 0400);
module_param(cnfg9, uint, 0400);

static int __init charge_snapshot_init(void)
{
	struct device *dev;
	struct regmap *map;
	const unsigned int registers[] = {
		MAX77705_CHG_REG_INT_OK, MAX77705_CHG_REG_DETAILS_00,
		MAX77705_CHG_REG_DETAILS_01, MAX77705_CHG_REG_CNFG_00,
		MAX77705_CHG_REG_CNFG_06, MAX77705_CHG_REG_CNFG_09,
	};
	unsigned int *values[] = { &int_ok, &details0, &details1, &cnfg0, &cnfg6, &cnfg9 };
	int ret = 0, i;

	if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte") ||
	    !of_machine_is_compatible("samsung,exynos9810"))
		return -ENODEV;
	dev = bus_find_device_by_name(&i2c_bus_type, NULL, "3-0069");
	if (!dev)
		return -ENODEV;
	device_lock(dev);
	if (!dev->driver || strcmp(dev->driver->name, "max77705-charger")) {
		ret = -EBUSY;
		goto out;
	}
	map = dev_get_regmap(dev, NULL);
	if (!map) {
		ret = -ENODEV;
		goto out;
	}
	for (i = 0; i < ARRAY_SIZE(registers); i++) {
		ret = regmap_read(map, registers[i], values[i]);
		if (ret)
			break;
	}
out:
	device_unlock(dev);
	put_device(dev);
	return ret;
}

static void __exit charge_snapshot_exit(void) { }
module_init(charge_snapshot_init);
module_exit(charge_snapshot_exit);
MODULE_DESCRIPTION("Guarded one-shot read-only G965N charger status snapshot");
MODULE_LICENSE("GPL");

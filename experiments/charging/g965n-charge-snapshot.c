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
/* Each read uses the bound owner's live regmap, never a cached module value.
 * No IRQ-status register is exposed: those reads can acknowledge interrupts.
 */
struct snapshot_register { unsigned int reg; };

static int read_register(unsigned int reg, unsigned int *value)
{
	struct device *dev;
	struct regmap *map;
	int ret;

	dev = bus_find_device_by_name(&i2c_bus_type, NULL, "3-0069");
	if (!dev)
		return -ENODEV;
	device_lock(dev);
	if (!dev->driver || strcmp(dev->driver->name, "max77705-charger")) {
		ret = -EBUSY;
		goto out;
	}
	map = dev_get_regmap(dev, NULL);
	ret = map ? regmap_read(map, reg, value) : -ENODEV;
out:
	device_unlock(dev);
	put_device(dev);
	return ret;
}

static int snapshot_get(char *buffer, const struct kernel_param *param)
{
	const struct snapshot_register *item = param->arg;
	unsigned int value;
	int ret = read_register(item->reg, &value);

	return ret ? ret : sysfs_emit(buffer, "%u\n", value);
}

static const struct kernel_param_ops snapshot_ops = { .get = snapshot_get };
#define SNAPSHOT(name, regname) \
	static struct snapshot_register snapshot_##name = { regname }; \
	module_param_cb(name, &snapshot_ops, &snapshot_##name, 0400)

SNAPSHOT(int_ok, MAX77705_CHG_REG_INT_OK);
SNAPSHOT(details0, MAX77705_CHG_REG_DETAILS_00);
SNAPSHOT(details1, MAX77705_CHG_REG_DETAILS_01);
SNAPSHOT(details2, MAX77705_CHG_REG_DETAILS_02);
SNAPSHOT(cnfg0, MAX77705_CHG_REG_CNFG_00);
SNAPSHOT(cnfg1, MAX77705_CHG_REG_CNFG_01);
SNAPSHOT(cnfg2, MAX77705_CHG_REG_CNFG_02);
SNAPSHOT(cnfg3, MAX77705_CHG_REG_CNFG_03);
SNAPSHOT(cnfg4, MAX77705_CHG_REG_CNFG_04);
SNAPSHOT(cnfg6, MAX77705_CHG_REG_CNFG_06);
SNAPSHOT(cnfg9, MAX77705_CHG_REG_CNFG_09);
SNAPSHOT(cnfg12, MAX77705_CHG_REG_CNFG_12);

static int __init charge_snapshot_init(void)
{
	unsigned int value;

	if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte") ||
	    !of_machine_is_compatible("samsung,exynos9810"))
		return -ENODEV;
	return read_register(MAX77705_CHG_REG_INT_OK, &value);
}

static void __exit charge_snapshot_exit(void) { }
module_init(charge_snapshot_init);
module_exit(charge_snapshot_exit);
MODULE_DESCRIPTION("Guarded read-only live G965N charger status/configuration");
MODULE_LICENSE("GPL");

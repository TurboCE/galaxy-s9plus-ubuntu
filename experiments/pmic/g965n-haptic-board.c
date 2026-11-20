// SPDX-License-Identifier: GPL-2.0-only
/* Real rev26 motor boost GPIO, PWM pad and regulator/PWM consumer wiring.
 * Explicitly opt-in; no dummy supply, PMIC parent reprobe or BOOT write.
 */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/machine.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/mfd/max77693-common.h>
#include <linux/mfd/max77705-private.h>
#include <linux/of.h>
#include <linux/pinctrl/consumer.h>
#include <linux/pinctrl/machine.h>
#include <linux/platform_device.h>
#include <linux/pwm.h>
#include <linux/regulator/driver.h>
#include <linux/regulator/machine.h>
#include <linux/regmap.h>

static bool enable_g965n;
module_param(enable_g965n, bool, 0400);
static struct platform_device *self;
static struct gpio_desc *boost;
static struct gpio_desc *pwm_pad;
static struct pinctrl *pad;
static struct regulator_dev *supply;
static struct regmap *pmic_map;
static void __iomem *pins;
static int old_boost_dir, old_boost_value, old_pad_dir, old_pad_value;
static u32 old_pad_function;
static bool lookup_added, pinmap_added, boost_changed, pad_selected;

static struct gpiod_lookup_table gpios = {
	.dev_id = "g965n-haptic-board",
	.table = {
		GPIO_LOOKUP("gpg1", 7, "motor-boost", GPIO_ACTIVE_HIGH),
		GPIO_LOOKUP("gpp3", 1, "pwm-pad", GPIO_ACTIVE_HIGH),
		{ }
	},
};
/* Samsung PINCFG_PACK(PINCFG_TYPE_FUNC=0, function2). Unlike synthetic
 * func2 mux names, this uses the provider's real pinconf API and bank lock.
 * Keep the exclusive GPIO reservation while selecting the PWM function.
 */
static unsigned long pwm_pad_config[] = { 2UL << 8 };
static const struct pinctrl_map pinmap[] = {
	PIN_MAP_CONFIGS_PIN("g965n-haptic-board", PINCTRL_STATE_DEFAULT,
			    "10430000.pinctrl", "gpp3-1", pwm_pad_config),
};
static void release_pwm(void *data) { pwm_put(data); }
struct pwm_device *g965n_haptic_pwm_get(struct device *consumer_dev);

/* Linux 7.1 does not export legacy pwm_add_table to modules. Use the
 * exported standard three-cell translator with the reviewed board mapping,
 * then retain normal consumer/provider linkage and managed PWM release.
 */
struct pwm_device *g965n_haptic_pwm_get(struct device *consumer_dev)
{
	struct of_phandle_args args = { .args_count = 3,
		.args = { 1, 48828, PWM_POLARITY_NORMAL } };
	struct device *provider;
	struct pwm_chip *chip;
	struct pwm_device *result;
	int ret;

	if (strcmp(dev_name(consumer_dev), "max77705-haptic"))
		return ERR_PTR(-ENODEV);
	provider = bus_find_device_by_name(&platform_bus_type, NULL, "samsung-pwm");
	if (!provider)
		return ERR_PTR(-EPROBE_DEFER);
	chip = dev_get_drvdata(provider);
	if (!chip || chip->npwm != 5) {
		put_device(provider);
		return ERR_PTR(-EPROBE_DEFER);
	}
	result = of_pwm_xlate_with_flags(chip, &args);
	if (!IS_ERR(result)) {
		if (!device_link_add(consumer_dev, pwmchip_parent(chip),
				     DL_FLAG_AUTOREMOVE_CONSUMER)) {
			pwm_put(result);
			result = ERR_PTR(-ENOMEM);
		} else {
			ret = devm_add_action_or_reset(consumer_dev, release_pwm, result);
			if (ret)
				result = ERR_PTR(ret);
		}
	}
	put_device(provider);
	return result;
}
EXPORT_SYMBOL_GPL(g965n_haptic_pwm_get);

static int motor_enable(struct regulator_dev *rdev)
{
	gpiod_set_value_cansleep(boost, 1);
	usleep_range(1000, 1500);
	return gpiod_get_value_cansleep(boost) == 1 ? 0 : -EIO;
}
static int motor_disable(struct regulator_dev *rdev)
{
	gpiod_set_value_cansleep(boost, 0);
	return gpiod_get_value_cansleep(boost) == 0 ? 0 : -EIO;
}
static int motor_enabled(struct regulator_dev *rdev)
{
	return gpiod_get_value_cansleep(boost);
}
static const struct regulator_ops motor_ops = {
	.enable = motor_enable, .disable = motor_disable,
	.is_enabled = motor_enabled,
};
static const struct regulator_desc motor_desc = {
	.name = "g965n-vdd-motor-3p3", .type = REGULATOR_VOLTAGE,
	.owner = THIS_MODULE, .ops = &motor_ops,
	.n_voltages = 1, .fixed_uV = 3300000,
};
static struct regulator_consumer_supply consumer[] = {
	REGULATOR_SUPPLY("haptic", "max77705-haptic"),
};
static struct regulator_init_data supply_data = {
	.constraints = {
		.name = "VDD_MOTOR_3P3", .min_uV = 3300000, .max_uV = 3300000,
		.valid_ops_mask = REGULATOR_CHANGE_STATUS,
	},
	.num_consumer_supplies = ARRAY_SIZE(consumer),
	.consumer_supplies = consumer,
};

/* Independent bounded-trial fallback can always cut the real motor rail. */
static ssize_t emergency_off_store(struct device *dev,
		struct device_attribute *attr, const char *buf, size_t count)
{
	if (!sysfs_streq(buf, "1"))
		return -EINVAL;
	gpiod_set_value_cansleep(boost, 0);
	if (gpiod_get_value_cansleep(boost) != 0)
		return -EIO;
	return count;
}
static DEVICE_ATTR_WO(emergency_off);

static ssize_t motor_state_show(struct device *dev,
		struct device_attribute *attr, char *buf)
{
	unsigned int main, config;
	int ret;

	ret = regmap_read(pmic_map, MAX77705_PMIC_REG_MAINCTRL1, &main);
	if (ret)
		return ret;
	ret = regmap_read(pmic_map, MAX77705_PMIC_REG_MCONFIG, &config);
	if (ret)
		return ret;
	return sysfs_emit(buf, "boost=%d bias=%u motor=%u config=%02x\n",
		gpiod_get_value_cansleep(boost), !!(main & BIT(7)),
		!!(config & BIT(6)), config);
}
static DEVICE_ATTR_RO(motor_state);

static void release_board(void)
{
	if (boost)
		gpiod_set_value_cansleep(boost, 0);
	if (self)
		device_remove_file(&self->dev, &dev_attr_emergency_off);
	if (self)
		device_remove_file(&self->dev, &dev_attr_motor_state);
	if (supply) {
		regulator_unregister(supply);
		supply = NULL;
	}
	if (pad) {
		pinctrl_put(pad);
		pad = NULL;
	}
	if (pwm_pad) {
		if (old_pad_function != 2) {
			if (old_pad_dir)
				gpiod_direction_input(pwm_pad);
			else
				gpiod_direction_output(pwm_pad, old_pad_value);
		}
		gpiod_put(pwm_pad);
		pwm_pad = NULL;
	}
	if (pinmap_added) {
		pinctrl_unregister_mappings(pinmap);
		pinmap_added = false;
	}
	if (boost) {
		if (boost_changed) {
			if (old_boost_dir)
				gpiod_direction_input(boost);
			else
				gpiod_direction_output(boost, old_boost_value);
		}
		gpiod_put(boost);
		boost = NULL;
	}
	if (pins) {
		iounmap(pins);
		pins = NULL;
	}
	if (self) {
		platform_device_unregister(self);
		self = NULL;
	}
	if (lookup_added) {
		gpiod_remove_lookup_table(&gpios);
		lookup_added = false;
	}
}

static int __init board_init(void)
{
	struct regulator_config config = {};
	struct device *child;
	struct max77693_dev *pmic;
	u32 mode;
	int ret;

	if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte"))
		return -ENODEV;
	child = bus_find_device_by_name(&platform_bus_type, NULL, "max77705-haptic");
	if (!child)
		return -ENODEV;
	pmic = dev_get_drvdata(child->parent);
	ret = child->driver ? -EBUSY : 0;
	if (!pmic || pmic->type != TYPE_MAX77705)
		ret = -ENODEV;
	if (!ret)
		pmic_map = pmic->regmap;
	put_device(child);
	if (ret)
		return ret;
	pins = ioremap(0x10430000, 0x1000);
	if (!pins)
		return -ENOMEM;
	/* Accept GPIO mode or this exact pad's bootloader PWM2 function only.
	 * A successful exclusive GPIO request below still checks pad ownership.
	 */
	mode = (readl(pins + 0x60) >> 4) & 0xf;
	if (mode > 2) { ret = -EBUSY; goto fail; }
	old_pad_function = mode;
	old_pad_dir = mode == 0;
	old_pad_value = !!(readl(pins + 0x64) & BIT(1));
	mode = (readl(pins + 0xa0) >> 28) & 0xf;
	if (mode > 1) { ret = -EBUSY; goto fail; }
	old_boost_dir = mode == 0;
	old_boost_value = !!(readl(pins + 0xa4) & BIT(7));
	gpiod_add_lookup_table(&gpios);
	lookup_added = true;
	self = platform_device_register_simple("g965n-haptic-board", -1, NULL, 0);
	if (IS_ERR(self)) { ret = PTR_ERR(self); self = NULL; goto fail; }
	boost = gpiod_get(&self->dev, "motor-boost", GPIOD_ASIS);
	if (IS_ERR(boost)) { ret = PTR_ERR(boost); boost = NULL; goto fail; }
	ret = gpiod_direction_output(boost, 0);
	if (ret)
		goto fail;
	boost_changed = true;
	/* Claim/check the PWM pin before permitting an alternate function. */
	pwm_pad = gpiod_get(&self->dev, "pwm-pad", GPIOD_ASIS);
	if (IS_ERR(pwm_pad)) { ret = PTR_ERR(pwm_pad); pwm_pad = NULL; goto fail; }
	ret = pinctrl_register_mappings(pinmap, ARRAY_SIZE(pinmap));
	if (ret)
		goto fail;
	pinmap_added = true;
	pad = pinctrl_get_select_default(&self->dev);
	if (IS_ERR(pad)) { ret = PTR_ERR(pad); pad = NULL; goto fail; }
	pad_selected = true;
	config.dev = &self->dev;
	config.init_data = &supply_data;
	supply = regulator_register(&self->dev, &motor_desc, &config);
	if (IS_ERR(supply)) { ret = PTR_ERR(supply); supply = NULL; goto fail; }
	ret = device_create_file(&self->dev, &dev_attr_emergency_off);
	if (ret)
		goto fail;
	ret = device_create_file(&self->dev, &dev_attr_motor_state);
	if (ret)
		goto fail;
	pr_info("g965n-haptic: real boost GPIO, PWM1 and motor supply ready; rail off\n");
	return 0;
fail:
	release_board();
	return ret;
}
static void __exit board_exit(void) { release_board(); }
module_init(board_init);
module_exit(board_exit);
MODULE_DESCRIPTION("SM-G965N motor GPIO/regulator/PWM consumer wiring");
MODULE_LICENSE("GPL");

// SPDX-License-Identifier: GPL-2.0-only
/* Bounded board diagnostic. Reads the actual active-low TSP IRQ pad without
 * requesting, reconfiguring or driving it. Optional explicit power cycle
 * uses only the same masked LDO operations as the existing ACPM handover.
 * This is not a synthetic sensor or a production readiness implementation.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/gpio/driver.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/workqueue.h>
#include <linux/delay.h>
#include <linux/ktime.h>
#include <linux/soc/samsung/s9p-acpm.h>

static bool enable_g965n, power_cycle;
module_param(enable_g965n, bool, 0444);
module_param(power_cycle, bool, 0444);
static bool sample_done;
module_param(sample_done, bool, 0444);
static int raw_level = -1;
module_param(raw_level, int, 0444);
static struct gpio_device *bank;
static struct gpio_desc *pad;
static struct delayed_work sample_work;
static ktime_t started;
static unsigned int samples;

static void sample(struct work_struct *work)
{
	int value = gpiod_get_raw_value_cansleep(pad);
	s64 elapsed_ms = ktime_ms_delta(ktime_get_boottime(), started);

	if (!samples || value != raw_level)
		pr_info("g965n-touch-ready-probe: elapsed=%lldms rawIRQ=%d\n",
			elapsed_ms, value);
	WRITE_ONCE(raw_level, value);
	if (++samples >= 200) {
		WRITE_ONCE(sample_done, true);
		pr_info("g965n-touch-ready-probe: bounded sample complete\n");
		return;
	}
	schedule_delayed_work(&sample_work, msecs_to_jiffies(100));
}

static int cycle_rails(void)
{
	struct device *touch;
	u8 original[2];
	const u8 reg[] = {0x6c, 0x74};
	int ret, i;

	touch = bus_find_device_by_name(&i2c_bus_type, NULL, "0-0048");
	if (!touch)
		return -ENODEV;
	device_lock(touch);
	if (touch->driver) {
		ret = -EBUSY; /* Never power-cycle a bound touch driver. */
		goto out;
	}
	for (i = 0; i < 2; i++) {
		ret = s9p_acpm_pmic_read(reg[i], &original[i]);
		if (ret)
			goto out;
		if ((original[i] & 0xc0) != 0xc0) {
			ret = -EINVAL;
			goto out;
		}
	}
	for (i = 0; i < 2; i++) {
		ret = s9p_acpm_pmic_update(reg[i], 0, 0xc0);
		if (ret)
			goto restore;
	}
	pr_info("g965n-touch-ready-probe: rails off rawIRQ=%d\n",
		gpiod_get_raw_value_cansleep(pad));
	msleep(2000);
restore:
	for (i = 0; i < 2; i++) {
		int restored = s9p_acpm_pmic_update(reg[i], original[i] & 0xc0, 0xc0);
		if (!ret && restored)
			ret = restored;
	}
out:
	device_unlock(touch);
	put_device(touch);
	return ret;
}

static int __init probe_init(void)
{
	int ret;
	if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte"))
		return -ENODEV;
	bank = gpio_device_find_by_label("gpa1");
	if (!bank)
		return -EPROBE_DEFER;
	pad = gpio_device_get_desc(bank, 0); /* Pinned stock/mainline TSP IRQ. */
	if (IS_ERR(pad)) {
		ret = PTR_ERR(pad);
		goto fail;
	}
	if (power_cycle) {
		ret = cycle_rails();
		if (ret)
			goto fail;
	}
	started = ktime_get_boottime();
	INIT_DELAYED_WORK(&sample_work, sample);
	schedule_delayed_work(&sample_work, 0);
	return 0;
fail:
	gpio_device_put(bank);
	return ret;
}

static void __exit probe_exit(void)
{
	cancel_delayed_work_sync(&sample_work);
	gpio_device_put(bank);
}
module_init(probe_init);
module_exit(probe_exit);
MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("Opt-in bounded G965N touch IRQ readiness observation");

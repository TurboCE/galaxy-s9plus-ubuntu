// SPDX-License-Identifier: GPL-2.0-only
/* SM-G965N ADC trial wiring. Preserve firmware-held clocks: no gate/PLL writes.
 * The readiness-only clock handle reports no frequency. It may not be used
 * by consumers that require a clock rate or software control of the gates.
 */
#include <linux/clk.h>
#include <linux/clk-provider.h>
#include <linux/clkdev.h>
#include <linux/io.h>
#include <linux/irq.h>
#include <linux/irqdomain.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

static bool enable_g965n;
module_param(enable_g965n, bool, 0400);
MODULE_PARM_DESC(enable_g965n, "Explicit guarded G965N ADC trial, firmware-held clocks only");

static void __iomem *cmu;
static struct clk_hw clock_hw;
static struct clk *clock;
static struct clk_lookup *lookup;
static struct platform_device *device;
static unsigned int adc_irq;

static int firmware_clock_ready(struct clk_hw *hw)
{
	return !!(readl(cmu + 0x18) & BIT(21)) &&
	       !!(readl(cmu + 0x1c) & BIT(21));
}

static int firmware_clock_enable(struct clk_hw *hw)
{
	return firmware_clock_ready(hw) ? 0 : -ENOLINK;
}

static void firmware_clock_disable(struct clk_hw *hw)
{
	/* Firmware-owned gates remain untouched. */
}

static const struct clk_ops firmware_clock_ops = {
	.enable = firmware_clock_enable,
	.disable = firmware_clock_disable,
	.is_enabled = firmware_clock_ready,
};

static void release_board(void)
{
	if (device) {
		platform_device_unregister(device);
		device = NULL;
	}
	if (lookup) {
		clkdev_drop(lookup);
		lookup = NULL;
	}
	if (clock) {
		clk_unregister(clock);
		clock = NULL;
	}
	if (adc_irq) {
		irq_dispose_mapping(adc_irq);
		adc_irq = 0;
	}
	if (cmu) {
		iounmap(cmu);
		cmu = NULL;
	}
}

static int __init g965n_adc_board_init(void)
{
	const struct clk_init_data init = {
		.name = "g965n-adc-firmware-held",
		.ops = &firmware_clock_ops,
		.flags = CLK_IGNORE_UNUSED,
	};
	struct device_node *node;
	struct irq_domain *domain;
	struct irq_fwspec spec = { .param_count = 3 };
	struct resource resources[] = {
		DEFINE_RES_MEM(0x14230000, 0x100),
		DEFINE_RES_IRQ(0),
	};
	int ret;

	if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte") ||
	    !of_machine_is_compatible("samsung,exynos9810"))
		return -ENODEV;
	cmu = ioremap(0x14202000, 0x1000);
	if (!cmu)
		return -ENOMEM;
	if (!firmware_clock_ready(&clock_hw)) {
		ret = -ENOLINK;
		goto fail;
	}
	node = of_find_compatible_node(NULL, NULL, "arm,gic-400");
	if (!node) {
		ret = -ENODEV;
		goto fail;
	}
	domain = irq_find_host(node);
	if (!domain || irq_find_mapping(domain, 40)) {
		of_node_put(node);
		ret = -EBUSY; /* Preserve any existing SPI8 owner. */
		goto fail;
	}
	spec.fwnode = of_fwnode_handle(node);
	spec.param[0] = 0; /* SPI */
	spec.param[1] = 8;
	spec.param[2] = IRQ_TYPE_LEVEL_HIGH;
	adc_irq = irq_create_fwspec_mapping(&spec);
	of_node_put(node);
	if (!adc_irq) {
		ret = -EINVAL;
		goto fail;
	}
	clock_hw.init = &init;
	clock = clk_register(NULL, &clock_hw);
	if (IS_ERR(clock)) {
		ret = PTR_ERR(clock);
		clock = NULL;
		goto fail;
	}
	lookup = clkdev_create(clock, "adc", "g965n-adc-v3-trial");
	if (!lookup) {
		ret = -ENOMEM;
		goto fail;
	}
	resources[1].start = adc_irq;
	resources[1].end = adc_irq;
	device = platform_device_register_simple("g965n-adc-v3-trial", -1,
		resources, ARRAY_SIZE(resources));
	if (IS_ERR(device)) {
		ret = PTR_ERR(device);
		device = NULL;
		goto fail;
	}
	return 0;
fail:
	release_board();
	return ret;
}

static void __exit g965n_adc_board_exit(void)
{
	release_board();
}
module_init(g965n_adc_board_init);
module_exit(g965n_adc_board_exit);
MODULE_DESCRIPTION("Guarded G965N ADC wiring; readiness-only inherited clock");
MODULE_LICENSE("GPL");

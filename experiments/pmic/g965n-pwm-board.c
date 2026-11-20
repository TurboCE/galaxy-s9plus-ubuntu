// SPDX-License-Identifier: GPL-2.0-only
/* SM-G965N PWM board wiring. Builds separately; explicit guarded opt-in only.
 * The stock PWM driver uses pwm_sclk (fin_pll 1:1) for timer counts and a
 * separate PERIC0 APB gate for register access. Never retune the shared PLL.
 */
#include <linux/clk.h>
#include <linux/clkdev.h>
#include <linux/err.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_clk.h>
#include <linux/platform_device.h>
#include <clocksource/samsung_pwm.h>

static bool enable_g965n;
module_param(enable_g965n, bool, 0400);
MODULE_PARM_DESC(enable_g965n, "Explicit checked SM-G965N PWM-only trial");

static struct platform_device *pwm;
static struct clk *osc;
static struct clk_lookup *lookup;
static void __iomem *cmu;
static u32 previous_gate;
static bool gate_changed;
#define PWM_GATE 0x2044
#define GATE_BITS (BIT(20) | BIT(21))

static void release_board(void)
{
	if (pwm) {
		platform_device_unregister(pwm);
		pwm = NULL;
	}
	if (lookup) {
		clkdev_drop(lookup);
		lookup = NULL;
	}
	if (osc) {
		clk_put(osc);
		osc = NULL;
	}
	if (cmu) {
		if (gate_changed)
			writel((readl(cmu + PWM_GATE) & ~GATE_BITS) |
			       previous_gate, cmu + PWM_GATE);
		iounmap(cmu);
		cmu = NULL;
	}
}

static int __init g965n_pwm_init(void)
{
	struct device_node *node;
	struct of_phandle_args spec = {};
	/* Exact s3c6400 variant used by the rev26 vendor DT; only channel1. */
	struct samsung_pwm_variant variant = {
		.bits = 32, .div_base = 0, .has_tint_cstat = true,
		.tclk_mask = BIT(7) | BIT(6) | BIT(5), .output_mask = BIT(1),
	};
	struct resource resource = DEFINE_RES_MEM(0x10510000, 0x1000);
	int ret;

	if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte"))
		return -ENODEV;
	node = of_find_node_by_path("/osc-clock");
	if (!node)
		return -ENODEV;
	spec.np = node;
	osc = of_clk_get_from_provider(&spec);
	of_node_put(node);
	if (IS_ERR(osc)) {
		ret = PTR_ERR(osc);
		osc = NULL;
		return ret;
	}
	if (clk_get_rate(osc) != 26000000) {
		ret = -EINVAL;
		goto fail;
	}
	cmu = ioremap(0x10400000, 0x4000);
	if (!cmu) {
		ret = -ENOMEM;
		goto fail;
	}
	previous_gate = readl(cmu + PWM_GATE) & GATE_BITS;
	writel(readl(cmu + PWM_GATE) | GATE_BITS, cmu + PWM_GATE);
	gate_changed = true;
	if ((readl(cmu + PWM_GATE) & GATE_BITS) != GATE_BITS) {
		ret = -EIO;
		goto fail;
	}
	lookup = clkdev_create(osc, "timers", "samsung-pwm");
	if (!lookup) {
		ret = -ENOMEM;
		goto fail;
	}
	pwm = platform_device_register_resndata(NULL, "samsung-pwm", -1,
			&resource, 1, &variant, sizeof(variant));
	if (IS_ERR(pwm)) {
		ret = PTR_ERR(pwm);
		pwm = NULL;
		goto fail;
	}
	if (!platform_get_drvdata(pwm)) {
		ret = -ENODEV;
		goto fail;
	}
	pr_info("g965n-pwm: stock 26MHz timer source, APB gate, channel1 ready; no motor rail/pad enabled\n");
	return 0;
fail:
	release_board();
	return ret;
}

static void __exit g965n_pwm_exit(void)
{
	release_board();
}
module_init(g965n_pwm_init);
module_exit(g965n_pwm_exit);
MODULE_DESCRIPTION("SM-G965N PWM board clock wiring, no motor power");
MODULE_LICENSE("GPL");

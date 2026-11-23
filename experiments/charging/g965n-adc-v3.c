// SPDX-License-Identifier: GPL-2.0-only
/*
 * Exynos9810 ADC v3 bounded, opt-in raw-channel trial.
 * Register sequence adapted from exynos_adc.c, pinned in REFERENCE.json.
 * Original source notice (this derivative elects GPL version 2):
 *
 * Copyright (C) 2013 Naveen Krishna Chatradhi <ch.naveen@samsung.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 * No charging decisions, guessed temperatures, clock rates or PMIC writes.
 */
#include <linux/clk.h>
#include <linux/completion.h>
#include <linux/interrupt.h>
#include <linux/io.h>
#include <linux/iio/iio.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/platform_device.h>

#define ADC_CON1 0x00
#define ADC_CON2 0x04
#define ADC_DATA 0x08
#define ADC_INT_EN 0x10
#define ADC_INT_ST 0x14
#define ADC_RESET BIT(2)
#define ADC_NON_RESET BIT(1)
#define ADC_START BIT(0)
#define ADC_TIME_MASK (7U << 4)
#define ADC_TIME (6U << 4)
#define ADC_CHANNEL_MASK 0xfU
#define ADC_VALUE_MASK 0xfffU

static bool enable_g965n;
module_param(enable_g965n, bool, 0444);
MODULE_PARM_DESC(enable_g965n, "Opt in only after exact model/backup/clock/IRQ qualification");

struct g965n_adc {
	void __iomem *regs;
	struct clk *clk;
	struct mutex lock;
	struct completion done;
	int irq;
	u32 value;
	bool pending;
};

static bool g965n_adc_channel_valid(unsigned int channel)
{
	return channel == 1 || channel == 3 || channel == 4 || channel == 11;
}

static void g965n_adc_hw_init(struct g965n_adc *adc)
{
	writel(0, adc->regs + ADC_INT_EN);
	writel(ADC_RESET, adc->regs + ADC_CON1);
	writel(ADC_NON_RESET, adc->regs + ADC_CON1);
	writel(ADC_TIME, adc->regs + ADC_CON2);
	writel(1, adc->regs + ADC_INT_ST);
}

static void g965n_adc_hw_stop(struct g965n_adc *adc)
{
	writel(0, adc->regs + ADC_INT_EN);
	writel(readl(adc->regs + ADC_CON1) & ~ADC_START, adc->regs + ADC_CON1);
	writel(readl(adc->regs + ADC_CON2) & ~ADC_TIME_MASK, adc->regs + ADC_CON2);
	writel(1, adc->regs + ADC_INT_ST);
}

static irqreturn_t g965n_adc_irq(int irq, void *data)
{
	struct g965n_adc *adc = data;

	/* A stale GIC pending interrupt must not complete a new conversion. */
	if (!(readl(adc->regs + ADC_INT_ST) & 1))
		return IRQ_NONE;
	if (READ_ONCE(adc->pending)) {
		adc->value = readl(adc->regs + ADC_DATA) & ADC_VALUE_MASK;
		WRITE_ONCE(adc->pending, false);
		writel(1, adc->regs + ADC_INT_ST);
		complete(&adc->done);
	} else {
		writel(1, adc->regs + ADC_INT_ST);
	}
	return IRQ_HANDLED;
}

static int g965n_adc_read_raw(struct iio_dev *indio,
		const struct iio_chan_spec *channel, int *value, int *value2, long mask)
{
	struct g965n_adc *adc = iio_priv(indio);
	unsigned long completed;
	u32 saved_con1, saved_con2;
	int ret;

	if (mask != IIO_CHAN_INFO_RAW || !g965n_adc_channel_valid(channel->address))
		return -EINVAL;
	mutex_lock(&adc->lock);
	ret = clk_prepare_enable(adc->clk);
	if (ret)
		goto unlock;
	saved_con1 = readl(adc->regs + ADC_CON1);
	saved_con2 = readl(adc->regs + ADC_CON2);
	if (readl(adc->regs + ADC_INT_EN) ||
	    (saved_con1 & (ADC_START | ADC_RESET))) {
		ret = -EBUSY; /* An existing conversion/interrupt owner is preserved. */
		goto clock_off;
	}
	g965n_adc_hw_init(adc);
	reinit_completion(&adc->done);
	WRITE_ONCE(adc->pending, true);
	enable_irq(adc->irq);
	writel(1, adc->regs + ADC_INT_EN);
	writel((readl(adc->regs + ADC_CON2) & ~ADC_CHANNEL_MASK) |
		channel->address, adc->regs + ADC_CON2);
	writel(readl(adc->regs + ADC_CON1) | ADC_START, adc->regs + ADC_CON1);
	completed = wait_for_completion_timeout(&adc->done, msecs_to_jiffies(100));
	writel(0, adc->regs + ADC_INT_EN);
	disable_irq(adc->irq); /* Synchronize before ending ownership/gating clock. */
	WRITE_ONCE(adc->pending, false);
	if (completed) {
		*value = adc->value;
		*value2 = 0;
		ret = IIO_VAL_INT;
	} else {
		ret = -ETIMEDOUT; /* Never convert missing data into a valid zero. */
	}
	g965n_adc_hw_stop(adc);
	writel(saved_con2, adc->regs + ADC_CON2);
	writel(saved_con1, adc->regs + ADC_CON1);
clock_off:
	clk_disable_unprepare(adc->clk);
unlock:
	mutex_unlock(&adc->lock);
	return ret;
}

#define RAW_CHANNEL(n, label) { .type = IIO_VOLTAGE, .indexed = 1, \
	.channel = (n), .address = (n), .datasheet_name = (label), \
	.info_mask_separate = BIT(IIO_CHAN_INFO_RAW) }
static const struct iio_chan_spec g965n_adc_channels[] = {
	RAW_CHANNEL(1, "adc-usb-temp"),
	RAW_CHANNEL(3, "adc-chg-temp"),
	RAW_CHANNEL(4, "adc-temp"),
	RAW_CHANNEL(11, "adc-in-bat"),
};
static const struct iio_info g965n_adc_info = { .read_raw = g965n_adc_read_raw };

static int g965n_adc_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct resource *mem;
	struct iio_dev *indio;
	struct g965n_adc *adc;
	int ret;

	if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte") ||
	    !of_machine_is_compatible("samsung,exynos9810"))
		return -ENODEV;
	/* Public rev26 has no PHY-control or inter-processor semaphore property.
	 * A different wiring contract requires its own reviewed implementation.
	 */
	if (of_find_property(dev->of_node, "sysreg", NULL) ||
	    of_find_property(dev->of_node, "samsung,adc-phy-control", NULL))
		return -EOPNOTSUPP;
	mem = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!mem || mem->start != 0x14230000 || resource_size(mem) != 0x100)
		return -EINVAL;
	indio = devm_iio_device_alloc(dev, sizeof(*adc));
	if (!indio)
		return -ENOMEM;
	adc = iio_priv(indio);
	adc->regs = devm_ioremap_resource(dev, mem);
	if (IS_ERR(adc->regs))
		return PTR_ERR(adc->regs);
	adc->clk = devm_clk_get(dev, "adc");
	if (IS_ERR(adc->clk))
		return dev_err_probe(dev, PTR_ERR(adc->clk), "ADC clock unavailable\n");
	adc->irq = platform_get_irq(pdev, 0);
	if (adc->irq < 0)
		return adc->irq;
	mutex_init(&adc->lock);
	init_completion(&adc->done);
	ret = devm_request_irq(dev, adc->irq, g965n_adc_irq, IRQF_NO_AUTOEN,
		dev_name(dev), adc);
	if (ret)
		return ret;
	indio->name = "g965n-adc-v3-trial";
	indio->info = &g965n_adc_info;
	indio->modes = INDIO_DIRECT_MODE;
	indio->channels = g965n_adc_channels;
	indio->num_channels = ARRAY_SIZE(g965n_adc_channels);
	return devm_iio_device_register(dev, indio);
}

static const struct of_device_id g965n_adc_of_match[] = {
	{ .compatible = "turboce,g965n-adc-v3-trial" },
	{}
};
MODULE_DEVICE_TABLE(of, g965n_adc_of_match);
static struct platform_driver g965n_adc_driver = {
	.probe = g965n_adc_probe,
	.driver = {
		.name = "g965n-adc-v3-trial",
		.of_match_table = g965n_adc_of_match,
	},
};
module_platform_driver(g965n_adc_driver);
MODULE_DESCRIPTION("Opt-in Exynos9810 ADC v3 raw charging-channel trial");
MODULE_LICENSE("GPL");

// SPDX-License-Identifier: GPL-2.0-only
/* SM-G965N S3NRN82 NCI transport. Firmware and secure-element access are omitted. */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/machine.h>
#include <linux/i2c.h>
#include <linux/interrupt.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/regmap.h>
#include <net/nfc/nci_core.h>

#define NFC_ADDRESS 0x27
#define LDO38 0x6f
#define LDO_ENABLE GENMASK(7, 6)
#define LDO_1V8 0x2c
#define CLKOUT1 0xa0c
#define CLKOUT1_MASK (GENMASK(13, 8) | BIT(0))
#define RESET_DELAY_MS 150
#define PROP_FW_CFG 0x28

/* Pinned Samsung Exynos9810 sources define this board's LDO38 and CLKOUT1. */
extern int s9p_acpm_pmic_read(u8 reg, u8 *value);
extern int s9p_acpm_pmic_update(u8 reg, u8 value, u8 mask);

struct g965n_nfc {
	struct i2c_client *client;
	struct nci_dev *nci;
	struct regmap *pmu;
	struct gpio_desc *ven, *firm, *irq_gpio;
	struct mutex transfer_lock;
	unsigned int previous_clock;
	u8 previous_power;
	int irq;
};

static int acpm_status(int status)
{
	return status > 0 ? -EIO : status;
}

static void nfc_power_off(struct g965n_nfc *board)
{
	gpiod_set_value_cansleep(board->ven, 0);
	gpiod_set_value_cansleep(board->firm, 0);
	if (regmap_update_bits(board->pmu, CLKOUT1, CLKOUT1_MASK, board->previous_clock))
		dev_warn(&board->client->dev, "could not restore NFC clock\n");
	if (s9p_acpm_pmic_update(LDO38, board->previous_power, LDO_ENABLE))
		dev_warn(&board->client->dev, "could not restore NFC supply mode\n");
}

static int nfc_power_on(struct g965n_nfc *board)
{
	int ret;

	ret = acpm_status(s9p_acpm_pmic_read(LDO38, &board->previous_power));
	if (ret)
		return ret;
	if ((board->previous_power & ~LDO_ENABLE) != LDO_1V8)
		return -EINVAL;
	ret = regmap_read(board->pmu, CLKOUT1, &board->previous_clock);
	if (ret)
		return ret;
	ret = acpm_status(s9p_acpm_pmic_update(LDO38, LDO_ENABLE, LDO_ENABLE));
	if (ret)
		goto restore;
	ret = regmap_update_bits(board->pmu, CLKOUT1, CLKOUT1_MASK, 0);
	if (ret)
		goto restore;
	gpiod_set_value_cansleep(board->firm, 0);
	gpiod_set_value_cansleep(board->ven, 0);
	msleep(RESET_DELAY_MS);
	gpiod_set_value_cansleep(board->ven, 1);
	msleep(RESET_DELAY_MS / 2);
	gpiod_set_value_cansleep(board->firm, 1); /* wake only after normal-mode VEN */
	msleep(100);
	return 0;

restore:
	nfc_power_off(board);
	return ret;
}

static int nfc_xfer_count(int ret, int expected)
{
	return ret < 0 ? ret : ret == expected ? 0 : -EIO;
}

static struct sk_buff *read_frame(struct g965n_nfc *board)
{
	u8 header[3];
	struct sk_buff *skb;
	int ret;

	ret = nfc_xfer_count(i2c_master_recv(board->client, header, sizeof(header)), sizeof(header));
	if (ret)
		return ERR_PTR(ret);
	skb = alloc_skb(sizeof(header) + header[2], GFP_KERNEL);
	if (!skb)
		return ERR_PTR(-ENOMEM);
	skb_put_data(skb, header, sizeof(header));
	if (header[2]) {
		ret = nfc_xfer_count(i2c_master_recv(board->client, skb_put(skb, header[2]), header[2]), header[2]);
		if (ret) {
			kfree_skb(skb);
			return ERR_PTR(ret);
		}
	}
	return skb;
}

static int check_controller(struct g965n_nfc *board)
{
	static const u8 reset[] = { 0x20, 0x00, 0x01, 0x00 };
	struct sk_buff *reply;
	unsigned int attempt;
	int ret;

	ret = nfc_power_on(board);
	if (ret)
		return ret;
	ret = nfc_xfer_count(i2c_master_send(board->client, reset, sizeof(reset)), sizeof(reset));
	if (ret)
		goto off;
	for (attempt = 0; attempt < 100; ++attempt) {
		ret = gpiod_get_value_cansleep(board->irq_gpio);
		if (ret)
			break;
		usleep_range(5000, 7000);
	}
	if (ret <= 0) {
		ret = ret ? ret : -ETIMEDOUT;
		goto off;
	}
	reply = read_frame(board);
	if (IS_ERR(reply)) {
		ret = PTR_ERR(reply);
		goto off;
	}
	ret = reply->len >= 4 && reply->data[0] == 0x40 &&
	      reply->data[1] == 0 && reply->data[3] == 0 ? 0 : -EPROTO;
	kfree_skb(reply);
off:
	nfc_power_off(board);
	return ret;
}

static irqreturn_t nfc_interrupt(int irq, void *data)
{
	struct g965n_nfc *board = data;
	struct sk_buff *frame;

	mutex_lock(&board->transfer_lock);
	frame = read_frame(board);
	mutex_unlock(&board->transfer_lock);
	if (!IS_ERR(frame)) {
		dev_info(&board->client->dev, "NCI RX %02x %02x length %u\n", frame->data[0], frame->data[1], frame->len);
		nci_recv_frame(board->nci, frame);
	} else {
		dev_warn(&board->client->dev, "NCI receive error %ld\n", PTR_ERR(frame));
	}
	return IRQ_HANDLED;
}

static int g965n_open(struct nci_dev *nci)
{
	struct g965n_nfc *board = nci_get_drvdata(nci);
	int ret = nfc_power_on(board);

	if (!ret)
		enable_irq(board->irq);
	return ret;
}

static int g965n_close(struct nci_dev *nci)
{
	struct g965n_nfc *board = nci_get_drvdata(nci);

	disable_irq(board->irq);
	nfc_power_off(board);
	return 0;
}

static int g965n_send(struct nci_dev *nci, struct sk_buff *skb)
{
	struct g965n_nfc *board = nci_get_drvdata(nci);
	int ret;

	mutex_lock(&board->transfer_lock);
	ret = nfc_xfer_count(i2c_master_send(board->client, skb->data, skb->len), skb->len);
	mutex_unlock(&board->transfer_lock);
	dev_info(&board->client->dev, "NCI TX %02x %02x length %u result %d\n", skb->data[0], skb->data[1], skb->len, ret);
	kfree_skb(skb);
	return ret;
}

static int clock_config_response(struct nci_dev *nci, struct sk_buff *skb)
{
	if (!skb->len)
		return -EPROTO;
	nci_req_complete(nci, skb->data[0]);
	return 0;
}

static int g965n_init(struct nci_dev *nci)
{
	/* Owner's SM-G965N vendor config: FW_CFG_CLK_SPEED=0x12.
	 * Samsung's HAL sends this single-byte command before CORE_RESET.
	 * This configures the running controller; no firmware image is uploaded.
	 */
	const u8 clock = 0x12;

	return nci_prop_cmd(nci, PROP_FW_CFG, sizeof(clock), &clock);
}

static const struct nci_driver_ops g965n_prop_ops[] = {
	{
		.opcode = nci_opcode_pack(NCI_GID_PROPRIETARY, PROP_FW_CFG),
		.rsp = clock_config_response,
	},
};

static const struct nci_ops g965n_ops = {
	.init = g965n_init,
	.open = g965n_open,
	.close = g965n_close,
	.send = g965n_send,
	.prop_ops = g965n_prop_ops,
	.n_prop_ops = ARRAY_SIZE(g965n_prop_ops),
};

static struct gpiod_lookup_table nfc_pins = {
	.table = {
		GPIO_LOOKUP(NULL, 11, "ven", GPIO_ACTIVE_LOW),
		GPIO_LOOKUP(NULL, 9, "firm", GPIO_ACTIVE_HIGH),
		GPIO_LOOKUP("gpa1", 2, "irq", GPIO_ACTIVE_HIGH),
		{ }
	},
};

static int acquire_pins(struct g965n_nfc *board)
{
	struct device_node *node = of_find_node_by_path("/soc@0/i2c@10930000");
	struct device *dev = &board->client->dev;
	struct i2c_adapter *bus;
	char label[24];

	if (!node)
		return -ENODEV;
	bus = of_find_i2c_adapter_by_node(node);
	of_node_put(node);
	if (!bus)
		return -EPROBE_DEFER;
	snprintf(label, sizeof(label), "%d-0022", bus->nr);
	i2c_put_adapter(bus);
	nfc_pins.dev_id = dev_name(dev);
	nfc_pins.table[0].key = label;
	nfc_pins.table[1].key = label;
	gpiod_add_lookup_table(&nfc_pins);
	board->ven = devm_gpiod_get(dev, "ven", GPIOD_OUT_LOW);
	board->firm = devm_gpiod_get(dev, "firm", GPIOD_OUT_LOW);
	board->irq_gpio = devm_gpiod_get(dev, "irq", GPIOD_IN);
	gpiod_remove_lookup_table(&nfc_pins);
	return PTR_ERR_OR_ZERO(board->ven) ?: PTR_ERR_OR_ZERO(board->firm) ?:
	       PTR_ERR_OR_ZERO(board->irq_gpio);
}

static int g965n_probe(struct i2c_client *client)
{
	const u32 protocols = NFC_PROTO_JEWEL_MASK | NFC_PROTO_MIFARE_MASK |
		NFC_PROTO_FELICA_MASK | NFC_PROTO_ISO14443_MASK |
		NFC_PROTO_ISO14443_B_MASK | NFC_PROTO_ISO15693_MASK;
	struct device *dev = &client->dev;
	struct g965n_nfc *board;
	struct device_node *bus_node;
	bool same_bus;
	int ret;

	if (!of_machine_is_compatible("samsung,star2lte") || client->addr != NFC_ADDRESS)
		return -ENODEV;
	bus_node = of_find_node_by_path("/soc@0/i2c@108e0000");
	same_bus = bus_node && bus_node == client->adapter->dev.of_node;
	of_node_put(bus_node);
	if (!same_bus)
		return -ENODEV;
	board = devm_kzalloc(dev, sizeof(*board), GFP_KERNEL);
	if (!board)
		return -ENOMEM;
	board->client = client;
	board->pmu = syscon_regmap_lookup_by_compatible("samsung,exynos9810-pmu");
	if (IS_ERR(board->pmu))
		return PTR_ERR(board->pmu);
	ret = acquire_pins(board);
	if (ret)
		return dev_err_probe(dev, ret, "could not acquire NFC GPIOs\n");
	ret = check_controller(board);
	if (ret)
		return dev_err_probe(dev, ret, "controller CORE_RESET did not complete\n");
	board->irq = gpiod_to_irq(board->irq_gpio);
	if (board->irq < 0)
		return board->irq;
	mutex_init(&board->transfer_lock);
	ret = devm_request_threaded_irq(dev, board->irq, NULL, nfc_interrupt,
				      IRQF_TRIGGER_HIGH | IRQF_ONESHOT | IRQF_NO_AUTOEN,
				      dev_name(dev), board);
	if (ret)
		return ret;
	board->nci = nci_allocate_device(&g965n_ops, protocols, 0, 0);
	if (!board->nci)
		return -ENOMEM;
	nci_set_drvdata(board->nci, board);
	nci_set_parent_dev(board->nci, dev);
	i2c_set_clientdata(client, board);
	ret = nci_register_device(board->nci);
	if (ret)
		nci_free_device(board->nci);
	return ret;
}

static void g965n_remove(struct i2c_client *client)
{
	struct g965n_nfc *board = i2c_get_clientdata(client);

	nci_unregister_device(board->nci);
	nci_free_device(board->nci);
}

static const struct i2c_device_id g965n_ids[] = {
	{ "g965n-s3nrn82", 0 },
	{ }
};
MODULE_DEVICE_TABLE(i2c, g965n_ids);

static struct i2c_driver g965n_driver = {
	.driver.name = "g965n-s3nrn82",
	.probe = g965n_probe,
	.remove = g965n_remove,
	.id_table = g965n_ids,
};
module_i2c_driver(g965n_driver);

MODULE_DESCRIPTION("Experimental G965N S3NRN82 I2C NCI transport");
MODULE_LICENSE("GPL");

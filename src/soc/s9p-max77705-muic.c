// SPDX-License-Identifier: GPL-2.0
/*
 * MAX77705 USB-C/MUIC path switch for the Galaxy S9+ (star2lte).
 *
 * The MAX77705 carries an embedded MCU ("USBC") that owns the Type-C CC
 * logic, BC1.2 charger detection and the D+/D- switches between the
 * connector and the AP. The AP talks to it over I2C at address 0x25 with an
 * opcode protocol: the opcode and its data go into AP_DATAOUT0.. (0x21..),
 * a write to AP_DATAOUT32 (0x41) terminates the command, the MCU answers in
 * AP_DATAIN0.. (0x51..).
 *
 * The switches are not set by the MCU itself. Samsung's MUIC driver sends
 * COMMAND_CONTROL1_WRITE (0x06) with COM_USB (D+ and D- to the AP) whenever
 * a USB host is attached, and its shutdown path resets the MCU
 * (max77705_reset_ic: register 0x80 = 0x0f), so a kernel entered from TWRP
 * finds the switches in their post-reset state and the host sees nothing on
 * D+/D- however well the SoC PHY is configured. This driver does the one
 * thing that is needed: it routes D+/D- to the AP, and repeats that whenever
 * VBUS reappears.
 */
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/power_supply.h>
#include <linux/ktime.h>
#include <linux/sysfs.h>
#include <linux/workqueue.h>
#include "s9p-max77705-source.h"

#ifndef S9P_MUIC_DRIVER_NAME
#define S9P_MUIC_DRIVER_NAME "s9p-max77705-muic"
#endif

#define REG_UIC_HW_REV		0x00
#define REG_UIC_FW_REV		0x01
#define REG_UIC_INT		0x02
#define REG_CC_INT		0x03
#define REG_PD_INT		0x04
#define REG_VDM_INT		0x05
#define REG_USBC_STATUS1	0x06
#define REG_USBC_STATUS2	0x07
#define REG_BC_STATUS		0x08
#define  BC_STATUS_VBUSDET		BIT(7)
#define  BC_STATUS_PRCHGTYP_MASK	(0x7 << 3)
#define  BC_STATUS_DCDTMO		BIT(2)
#define  BC_STATUS_CHGTYP_MASK		(0x3 << 0)
#define REG_CC_STATUS0		0x0a
#define REG_CC_STATUS1		0x0b
#define REG_PD_STATUS0		0x0c
#define REG_PD_STATUS1		0x0d
#define REG_UIC_INT_M		0x0e
#define REG_CC_INT_M		0x0f
#define REG_PD_INT_M		0x10
#define REG_VDM_INT_M		0x11
#define REG_AP_DATAOUT0		0x21	/* OPCODE_WRITE */
#define REG_AP_DATAOUT32	0x41	/* OPCODE_WRITE_END */
#define REG_AP_DATAIN0		0x51	/* OPCODE_READ */

#define OPCODE_BC_CTRL1_READ	0x01
#define OPCODE_BC_CTRL1_WRITE	0x02
#define OPCODE_CONTROL1_READ	0x05
#define OPCODE_CONTROL1_WRITE	0x06

/*
 * CONTROL1: NoBCComp[7] RCPS[6] COMP2SW(D+)[5:3] COMN1SW(D-)[2:0]
 * 001 = USB (AP), 011 = UART, 111 = open.
 */
#define COM_USB			0x09
#define COM_OPEN		0x3f

static int s9p_muic_path = COM_USB;
module_param_named(path, s9p_muic_path, int, 0644);
MODULE_PARM_DESC(path, "CONTROL1 switch value to apply (0x09 USB, 0x3f open, -1 none)");

static int s9p_muic_poll_ms = 500;
module_param_named(poll_ms, s9p_muic_poll_ms, int, 0644);

struct s9p_muic {
	struct i2c_client *client;
	struct delayed_work work;
	u8 last_bc;
	bool applied;
	struct mutex lock; /* All MCU requests and their replies have one owner. */
	struct power_supply *supply;
	u64 sampled_ms;
	u64 queried_ms;
	int bc, cc, pd, cc1;
	int source_ua, source_uv, usb_type;
	int selected_pdo;
	int contract_ua, contract_uv;
	int query_error, reply_header, reply_summary;
	bool contract_valid;
	u64 input_deadline_ms, input_generation;
	int input_requested_ua, input_applied_ua;
	bool input_owned;
};

static int muic_read(struct s9p_muic *m, u8 reg)
{
	return i2c_smbus_read_byte_data(m->client, reg);
}

static void muic_log_status(struct s9p_muic *m, const char *when)
{
	u8 st[8];
	int i, ret;

	for (i = 0; i < ARRAY_SIZE(st); i++) {
		ret = muic_read(m, REG_USBC_STATUS1 + i);
		st[i] = ret < 0 ? 0xee : ret;
	}
	dev_info(&m->client->dev,
		 "%s: usbc1=%02x usbc2=%02x bc=%02x(vbus=%d chgtyp=%d prchg=%d) cc0=%02x cc1=%02x pd0=%02x pd1=%02x int=%02x/%02x/%02x/%02x\n",
		 when, st[0], st[1], st[2], !!(st[2] & BC_STATUS_VBUSDET),
		 st[2] & BC_STATUS_CHGTYP_MASK,
		 (st[2] & BC_STATUS_PRCHGTYP_MASK) >> 3,
		 st[4], st[5], st[6], st[7],
		 muic_read(m, REG_UIC_INT), muic_read(m, REG_CC_INT),
		 muic_read(m, REG_PD_INT), muic_read(m, REG_VDM_INT));
}

/* max77705_i2c_opcode_write(): opcode + data, then the end marker */
static int muic_opcode_write(struct s9p_muic *m, u8 opcode, const u8 *data,
			     int len)
{
	u8 buf[33];
	int ret;

	if (len > 32)
		return -EMSGSIZE;
	buf[0] = opcode;
	if (len)
		memcpy(buf + 1, data, len);
	ret = i2c_smbus_write_i2c_block_data(m->client, REG_AP_DATAOUT0,
					     len + 1, buf);
	if (ret < 0)
		return ret;
	if (len < 32)
		ret = i2c_smbus_write_byte_data(m->client, REG_AP_DATAOUT32, 0);
	return ret < 0 ? ret : 0;
}

static int muic_opcode_result(struct s9p_muic *m, u8 *out, int len)
{
	return i2c_smbus_read_i2c_block_data(m->client, REG_AP_DATAIN0, len,
					     out);
}

static int muic_set_path(struct s9p_muic *m, u8 val)
{
	u8 res[4] = {};
	int ret;

	ret = muic_opcode_write(m, OPCODE_CONTROL1_WRITE, &val, 1);
	if (ret) {
		dev_err(&m->client->dev, "CONTROL1 write failed: %d\n", ret);
		return ret;
	}
	msleep(20);
	muic_opcode_result(m, res, sizeof(res));
	dev_info(&m->client->dev,
		 "CONTROL1 <= %02x, MCU answered %02x %02x %02x %02x\n",
		 val, res[0], res[1], res[2], res[3]);
	m->applied = true;
	return 0;
}

/* Samsung/Maxim 2017 CURRENT_SRCCAP (0x30), pinned in
 * experiments/charging/USBC_REFERENCE.json. This only queries the current
 * selected source PDO; it never selects a PDO or changes charging/firmware.
 * The selected PDO current is a source ceiling, not measured consumption.
 */
static void muic_sample_source(struct s9p_muic *m)
{
	u8 reply[32] = {};
	struct s9p_source_pdo selected;
	int bc, cc, cc1, pd, ret;
	u64 now = ktime_to_ms(ktime_get_boottime());
	bool changed;

	bc = muic_read(m, REG_BC_STATUS);
	cc = muic_read(m, REG_CC_STATUS0);
	cc1 = muic_read(m, REG_CC_STATUS1);
	pd = muic_read(m, REG_PD_STATUS1);
	changed = bc != m->bc || cc != m->cc || cc1 != m->cc1 || pd != m->pd;
	m->bc = bc; m->cc = cc; m->cc1 = cc1; m->pd = pd;
	m->sampled_ms = now;
	if (changed) {
		m->queried_ms = 0;
		m->contract_valid = false;
	}
	m->source_ua = 500000;
	m->source_uv = 5000000;
	m->usb_type = POWER_SUPPLY_USB_TYPE_UNKNOWN;
	if (bc < 0 || cc < 0 || cc1 < 0 || pd < 0 ||
	    !(bc & BC_STATUS_VBUSDET) || (cc & 7) != 1 || (cc1 & BIT(1))) {
		m->contract_valid = false;
		return;
	}
	switch (bc & 3) {
	case 1: m->usb_type = POWER_SUPPLY_USB_TYPE_SDP; break;
	case 2: m->usb_type = POWER_SUPPLY_USB_TYPE_CDP; break;
	case 3: m->usb_type = POWER_SUPPLY_USB_TYPE_DCP; break;
	}
	/* No high-current inference from CCI, BC or PD-ready alone. */
	if (!(pd & BIT(4))) {
		m->contract_valid = false;
		return;
	}
	if (!m->queried_ms || now - m->queried_ms >= 2000) {
		m->contract_valid = false;
		m->selected_pdo = 0;
		m->queried_ms = now;
		m->query_error = -ENODATA;
		ret = muic_opcode_write(m, 0x30, NULL, 0);
		if (ret) {
			m->query_error = ret;
			return;
		}
		msleep(30);
		ret = muic_opcode_result(m, reply, sizeof(reply));
		m->reply_header = reply[0];
		m->reply_summary = reply[1];
		if (ret != sizeof(reply) || reply[0] != 0x30)
			return;
		/* Fixed supply only; unknown/battery/variable/PPS fail closed. */
		if (!s9p_source_pdo_parse(reply, sizeof(reply), &selected))
			return;
		/* Verify the same attachment still exists after the transaction. */
		if (muic_read(m, REG_BC_STATUS) != bc ||
		    muic_read(m, REG_CC_STATUS0) != cc ||
		    muic_read(m, REG_CC_STATUS1) != cc1 ||
		    muic_read(m, REG_PD_STATUS1) != pd)
			return;
		m->selected_pdo = selected.index;
		m->source_ua = selected.current_ua;
		m->source_uv = selected.voltage_uv;
		m->contract_ua = m->source_ua;
		m->contract_uv = m->source_uv;
		m->contract_valid = true;
		m->query_error = 0;
	} else if (m->contract_valid) {
		/* Values below are cached only until the next query/attachment change. */
		m->source_ua = m->contract_ua;
		m->source_uv = m->contract_uv;
		return;
	}
}

/* Optional, bounded input-current lease. Never changes charge current, CV or
 * CHG enable. MCU source changes, bad replies or a missing userspace heartbeat
 * restore the conservative input ceiling. Direct external changes invalidate
 * ownership instead of being overwritten by a stale controller.
 */
static int muic_input_apply(struct s9p_muic *m, bool release)
{
	struct power_supply *charger;
	union power_supply_propval observed_input, wanted;
	u64 now = ktime_to_ms(ktime_get_boottime());
	int ret, target;
	bool qualified;

	if (!m->input_owned)
		return 0;
	charger = power_supply_get_by_name("max77705-charger");
	if (!charger)
		return -ENODEV;
	ret = power_supply_get_property(charger, POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT, &observed_input);
	if (ret)
		goto out;
	if (observed_input.intval != m->input_applied_ua) {
		/* Preserve reductions from another controller and revoke this lease. */
		m->input_deadline_ms = 0;
		m->input_generation++;
		release = true;
	}
	qualified = m->contract_valid && m->source_uv == 5000000 &&
		m->source_ua >= m->input_requested_ua &&
		now - m->sampled_ms <= 1500 && now - m->queried_ms <= 3000;
	target = !release && now < m->input_deadline_ms && qualified ?
		m->input_requested_ua : 500000;
	if (release && observed_input.intval < target)
		target = observed_input.intval;
	if (observed_input.intval != target) {
		wanted.intval = target;
		ret = power_supply_set_property(charger, POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT, &wanted);
		if (ret)
			goto out;
		ret = power_supply_get_property(charger, POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT, &observed_input);
		if (ret || observed_input.intval != target) {
			ret = ret ?: -EIO;
			goto out;
		}
	}
	m->input_applied_ua = observed_input.intval;
	if (release || now >= m->input_deadline_ms) {
		m->input_deadline_ms = 0;
		m->input_owned = false;
		m->input_generation++;
	}
out:
	power_supply_put(charger);
	return ret;
}

static ssize_t input_policy_state_show(struct device *dev,
		struct device_attribute *attr, char *buf)
{
	struct s9p_muic *m = dev_get_drvdata(dev);
	ssize_t ret;
	mutex_lock(&m->lock);
	ret = sysfs_emit(buf, "%llu %u %d %d %llu\n", m->input_generation,
		m->input_owned, m->input_requested_ua, m->input_applied_ua, m->input_deadline_ms);
	mutex_unlock(&m->lock);
	return ret;
}
static DEVICE_ATTR_RO(input_policy_state);

static ssize_t input_policy_request_store(struct device *dev,
		struct device_attribute *attr, const char *buf, size_t count)
{
	struct s9p_muic *m = dev_get_drvdata(dev);
	struct power_supply *charger;
	union power_supply_propval observed_input;
	unsigned long long generation;
	unsigned int target;
	char trailing;
	int ret = 0;
	u64 now;
	if (sscanf(buf, "%llu %u %c", &generation, &target, &trailing) != 2 ||
	    (target != 0 && target != 900000 && target != 1200000))
		return -EINVAL;
	mutex_lock(&m->lock);
	now = ktime_to_ms(ktime_get_boottime());
	if (generation != m->input_generation) { ret = -EAGAIN; goto out; }
	if (!target) { ret = muic_input_apply(m, true); goto out; }
	if (m->input_owned && now >= m->input_deadline_ms) {
		muic_input_apply(m, true);
		ret = -EAGAIN; goto out;
	}
	if (!m->contract_valid || m->source_uv != 5000000 || m->source_ua < target ||
	    now - m->sampled_ms > 1500 || now - m->queried_ms > 3000) {
		ret = -ENODATA; goto out;
	}
	if (!m->input_owned) {
		charger = power_supply_get_by_name("max77705-charger");
		if (!charger) { ret = -ENODEV; goto out; }
		ret = power_supply_get_property(charger, POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT, &observed_input);
		power_supply_put(charger);
		if (ret) goto out;
		/* Never undo a manually reduced input limit at initial acquisition. */
		if (observed_input.intval != 500000) { ret = -EBUSY; goto out; }
		m->input_owned = true;
		m->input_applied_ua = observed_input.intval;
	}
	m->input_requested_ua = target;
	m->input_deadline_ms = now + 15000;
	ret = muic_input_apply(m, false);
	/* Lease expiry must not depend on a root-adjustable USB-path poll period. */
	mod_delayed_work(system_wq, &m->work, msecs_to_jiffies(500));
out:
	mutex_unlock(&m->lock);
	return ret ? ret : count;
}
static DEVICE_ATTR_WO(input_policy_request);

static enum power_supply_property muic_source_props[] = {
	POWER_SUPPLY_PROP_ONLINE, POWER_SUPPLY_PROP_USB_TYPE,
	POWER_SUPPLY_PROP_CURRENT_MAX, POWER_SUPPLY_PROP_VOLTAGE_MAX,
};

static int muic_source_get(struct power_supply *psy,
		enum power_supply_property prop, union power_supply_propval *val)
{
	struct s9p_muic *m = power_supply_get_drvdata(psy);
	int ret = 0;
	mutex_lock(&m->lock);
	if (!m->sampled_ms || ktime_to_ms(ktime_get_boottime()) - m->sampled_ms > 3000) {
		ret = -ENODATA;
		goto out;
	}
	switch (prop) {
	case POWER_SUPPLY_PROP_ONLINE:
		val->intval = m->bc >= 0 && !!(m->bc & BC_STATUS_VBUSDET); break;
	case POWER_SUPPLY_PROP_USB_TYPE: val->intval = m->contract_valid ? POWER_SUPPLY_USB_TYPE_PD : m->usb_type; break;
	case POWER_SUPPLY_PROP_CURRENT_MAX: val->intval = m->source_ua; break;
	case POWER_SUPPLY_PROP_VOLTAGE_MAX: val->intval = m->source_uv; break;
	default: ret = -EINVAL;
	}
out:
	mutex_unlock(&m->lock);
	return ret;
}

static const struct power_supply_desc muic_supply_desc = {
	.name = "g965n-usbc-input", .type = POWER_SUPPLY_TYPE_USB,
	.usb_types = BIT(POWER_SUPPLY_USB_TYPE_UNKNOWN) | BIT(POWER_SUPPLY_USB_TYPE_SDP) |
		BIT(POWER_SUPPLY_USB_TYPE_CDP) | BIT(POWER_SUPPLY_USB_TYPE_DCP) | BIT(POWER_SUPPLY_USB_TYPE_PD),
	.properties = muic_source_props, .num_properties = ARRAY_SIZE(muic_source_props),
	.get_property = muic_source_get,
};

static ssize_t source_status_show(struct device *dev,
		struct device_attribute *attr, char *buf)
{
	struct s9p_muic *m = dev_get_drvdata(dev);
	ssize_t ret;
	mutex_lock(&m->lock);
	ret = sysfs_emit(buf, "{\"sampled_ms\":%llu,\"queried_ms\":%llu,\"bc\":%d,\"cc\":%d,\"cc1\":%d,\"pd\":%d,\"contract_valid\":%u,\"selected_pdo\":%d,\"source_ua\":%d,\"source_uv\":%d,\"query_error\":%d,\"reply_header\":%d,\"reply_summary\":%d}\n",
		m->sampled_ms, m->queried_ms, m->bc, m->cc, m->cc1, m->pd,
		m->contract_valid, m->selected_pdo, m->source_ua, m->source_uv,
		m->query_error, m->reply_header, m->reply_summary);
	mutex_unlock(&m->lock);
	return ret;
}
static DEVICE_ATTR_RO(source_status);

static void muic_poll(struct work_struct *work)
{
	struct s9p_muic *m = container_of(work, struct s9p_muic, work.work);
	int bc = muic_read(m, REG_BC_STATUS);
	mutex_lock(&m->lock);

	if (bc >= 0 && (u8)bc != m->last_bc) {
		dev_info(&m->client->dev, "BC_STATUS %02x -> %02x\n",
			 m->last_bc, bc);
		/* VBUS came back: the MCU may have dropped the switch setting */
		if ((bc & BC_STATUS_VBUSDET) && !(m->last_bc & BC_STATUS_VBUSDET)
		    && s9p_muic_path >= 0)
			muic_set_path(m, s9p_muic_path);
		m->last_bc = bc;
	}
	muic_sample_source(m);
	if (muic_input_apply(m, false))
		dev_err_ratelimited(&m->client->dev, "input lease update failed\n");
	mutex_unlock(&m->lock);
	power_supply_changed(m->supply);
	if (s9p_muic_poll_ms > 0 || m->input_owned)
		schedule_delayed_work(&m->work, msecs_to_jiffies(m->input_owned ? 500 : s9p_muic_poll_ms));
}

static int s9p_muic_probe(struct i2c_client *client)
{
	struct s9p_muic *m;
	struct power_supply_config supply_config = {};
	int hw, fw, bc;

	m = devm_kzalloc(&client->dev, sizeof(*m), GFP_KERNEL);
	if (!m)
		return -ENOMEM;
	m->client = client;
	mutex_init(&m->lock);
	INIT_DELAYED_WORK(&m->work, muic_poll);
	i2c_set_clientdata(client, m);

	hw = muic_read(m, REG_UIC_HW_REV);
	fw = muic_read(m, REG_UIC_FW_REV);
	if (hw < 0 || fw < 0)
		return dev_err_probe(&client->dev, hw < 0 ? hw : fw,
				     "MAX77705 USBC does not answer\n");
	dev_info(&client->dev, "MAX77705 USBC: HW rev %02x, FW rev %02x\n",
		 hw, fw);
	muic_log_status(m, "at probe");

	bc = muic_read(m, REG_BC_STATUS);
	m->last_bc = bc < 0 ? 0 : bc;

	if (s9p_muic_path >= 0) {
		muic_set_path(m, s9p_muic_path);
		muic_log_status(m, "after switch");
	}
	muic_sample_source(m);
	supply_config.drv_data = m;
	supply_config.fwnode = dev_fwnode(&client->dev);
	m->supply = devm_power_supply_register(&client->dev, &muic_supply_desc, &supply_config);
	if (IS_ERR(m->supply))
		return PTR_ERR(m->supply);
	bc = device_create_file(&client->dev, &dev_attr_source_status);
	if (bc)
		return bc;
	bc = device_create_file(&client->dev, &dev_attr_input_policy_state);
	if (bc)
		goto remove_source;
	bc = device_create_file(&client->dev, &dev_attr_input_policy_request);
	if (bc)
		goto remove_state;

	if (s9p_muic_poll_ms > 0)
		schedule_delayed_work(&m->work, msecs_to_jiffies(s9p_muic_poll_ms));
	return 0;
remove_state:
	device_remove_file(&client->dev, &dev_attr_input_policy_state);
remove_source:
	device_remove_file(&client->dev, &dev_attr_source_status);
	return bc;
}

static void s9p_muic_remove(struct i2c_client *client)
{
	struct s9p_muic *m = i2c_get_clientdata(client);

	device_remove_file(&client->dev, &dev_attr_input_policy_request);
	device_remove_file(&client->dev, &dev_attr_input_policy_state);
	device_remove_file(&client->dev, &dev_attr_source_status);
	cancel_delayed_work_sync(&m->work);
	mutex_lock(&m->lock);
	muic_input_apply(m, true);
	mutex_unlock(&m->lock);
}

static const struct of_device_id s9p_muic_of_match[] = {
	{ .compatible = "samsung,s9p-max77705-muic" },
	{ }
};
MODULE_DEVICE_TABLE(of, s9p_muic_of_match);

static struct i2c_driver s9p_muic_driver = {
	.driver = {
		.name		= S9P_MUIC_DRIVER_NAME,
		.of_match_table	= s9p_muic_of_match,
	},
	.probe	= s9p_muic_probe,
	.remove	= s9p_muic_remove,
};
module_i2c_driver(s9p_muic_driver);

MODULE_DESCRIPTION("MAX77705 USB-C D+/D- path switch (Galaxy S9+)");
MODULE_LICENSE("GPL");

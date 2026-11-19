# SPDX-License-Identifier: GPL-2.0-only
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'experiments/modem/modem_ctrl_ss310ap.c'


class ModemControllerProbeTests(unittest.TestCase):
    def test_actual_controller_probe_validates_and_unwinds_interrupts(self):
        source = SOURCE.read_text()
        controller = source[source.index('int ss310ap_init_modemctl_device('):]
        with tempfile.TemporaryDirectory() as directory:
            test = Path(directory) / 'controller.c'
            binary = Path(directory) / 'controller'
            test.write_text(STUBS + controller + CASES)
            subprocess.run([os.getenv('CC', 'cc'), '-std=c11', '-Wall', '-Wextra',
                            '-Werror', str(test), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


STUBS = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <string.h>

#define EPROBE_DEFER 517
#define IRQF_NO_SUSPEND 1
#define IRQF_NO_THREAD 2
#define MCU_CP 0
struct device_node { bool reset_gpio; };
struct device { struct device_node *of_node; void *drvdata; int kobj; };
struct platform_device { struct device dev; };
struct modem_irq { int num; bool active; };
struct modem_ctl {
    struct device *dev;
    int init_cmpl, off_cmpl, irq_phone_active;
    struct modem_irq irq_cp_fail, irq_cp_wdt;
};
struct modem_data { int unused; };
static struct modem_ctl *g_mc;
static int lookup[2], initialized, requests, request_error_at, mailbox_error;
static int freed[2], free_count, sim_group;
static void *of_find_property(struct device_node *node, const char *name, int *len)
{
    assert(!strcmp(name, "modem_ctrl,gpio_cp_rst_n") && !len);
    return node->reset_gpio ? node : NULL;
}
#define dev_err_probe(dev, error, ...) (assert(dev), (error))
#define mif_err(...) ((void)0)
static struct platform_device *to_platform_device(struct device *dev)
{ return (struct platform_device *)dev; }
static int platform_get_irq(struct platform_device *pdev, int index)
{ assert(pdev && index >= 0 && index < 2); return lookup[index]; }
static void ss310ap_get_ops(struct modem_ctl *mc) { assert(mc); initialized++; }
static void ss310ap_get_pdata(struct modem_ctl *mc, struct modem_data *pdata)
{ assert(pdata); mc->irq_phone_active = 7; }
static void init_completion(int *completion) { *completion = 1; }
static void mif_init_irq(struct modem_irq *irq, int num, const char *name, unsigned long flags)
{ assert(num > 0 && name && flags == 3); irq->num = num; }
static void cp_fail_handler(void) {}
static void cp_wdt_handler(void) {}
static void cp_active_handler(void *data) { assert(data); }
static int mif_request_irq(struct modem_irq *irq, void (*handler)(void), struct modem_ctl *mc)
{
    assert(irq && handler && mc->init_cmpl && mc->off_cmpl);
    return ++requests == request_error_at ? -EBUSY : 0;
}
static void mif_disable_irq(struct modem_irq *irq)
{ assert(irq->active); irq->active = false; }
static int mbox_request_irq(int region, int line, void (*handler)(void *), struct modem_ctl *mc)
{
    assert(region == MCU_CP && handler && line == 7 && mc->init_cmpl && mc->off_cmpl);
    return mailbox_error;
}
static void free_irq(int irq, struct modem_ctl *mc)
{ assert(mc && free_count < 2); freed[free_count++] = irq; }
static void dev_set_drvdata(struct device *dev, struct modem_ctl *mc)
{ dev->drvdata = mc; }
static int sysfs_create_group(int *kobj, int *group)
{ assert(kobj && group == &sim_group); return 0; }
'''


CASES = r'''
int main(void)
{
    struct device_node node = {0};
    struct platform_device pdev = {0};
    struct modem_ctl mc = {.dev = &pdev.dev};
    struct modem_data pdata = {0};
    assert(ss310ap_init_modemctl_device(&mc, &pdata) == -ENODEV);
    pdev.dev.of_node = &node;
    node.reset_gpio = true;
    assert(ss310ap_init_modemctl_device(&mc, &pdata) == -EOPNOTSUPP);
    node.reset_gpio = false;
    lookup[0] = -EPROBE_DEFER;
    assert(ss310ap_init_modemctl_device(&mc, &pdata) == -EPROBE_DEFER);
    lookup[0] = 101; lookup[1] = -ENXIO;
    assert(ss310ap_init_modemctl_device(&mc, &pdata) == -ENXIO);
    assert(!initialized && !requests && !free_count && !g_mc && !pdev.dev.drvdata);

    lookup[1] = 106;
    request_error_at = 1;
    assert(ss310ap_init_modemctl_device(&mc, &pdata) == -EBUSY);
    assert(requests == 1 && !free_count && !g_mc);
    requests = 0; request_error_at = 2;
    assert(ss310ap_init_modemctl_device(&mc, &pdata) == -EBUSY);
    assert(requests == 2 && free_count == 1 && freed[0] == 101 && !g_mc);
    requests = 0; request_error_at = 0; free_count = 0; mailbox_error = -EINVAL;
    assert(ss310ap_init_modemctl_device(&mc, &pdata) == -EINVAL);
    assert(requests == 2 && free_count == 2 && freed[0] == 106 && freed[1] == 101);
    assert(!g_mc && !pdev.dev.drvdata);

    requests = 0; free_count = 0; mailbox_error = 0;
    assert(ss310ap_init_modemctl_device(&mc, &pdata) == 0);
    assert(requests == 2 && !free_count && g_mc == &mc && pdev.dev.drvdata == &mc);
    assert(!mc.irq_cp_fail.active && !mc.irq_cp_wdt.active);
    return 0;
}
'''

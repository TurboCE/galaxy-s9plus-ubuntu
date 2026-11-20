// SPDX-License-Identifier: GPL-2.0-only
/* SM-G965N rev26 flip-cover switch. The separate accessory GPIO is unused. */
#include <linux/err.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/driver.h>
#include <linux/gpio_keys.h>
#include <linux/input-event-codes.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>

static bool enable_g965n;
module_param(enable_g965n, bool, 0444);
MODULE_PARM_DESC(enable_g965n, "Enable the verified SM-G965N rev26 flip-cover input");

static struct gpio_device *cover_bank;
static struct platform_device *cover_device;
static struct gpio_keys_button cover_button = {
    .code = SW_LID,
    .active_low = true,
    .desc = "Flip cover",
    .type = EV_SW,
    .debounce_interval = 20,
};
static const struct gpio_keys_platform_data cover_keys = {
    .buttons = &cover_button,
    .nbuttons = 1,
    .name = "G965N Flip Cover",
};

static int __init cover_init(void)
{
    struct device_node *root;
    struct gpio_desc *desc;
    u32 revision;
    int ret;

    if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte") ||
        !of_machine_is_compatible("samsung,exynos9810"))
        return -ENODEV;
    root = of_find_node_by_path("/");
    ret = of_property_read_u32(root, "model_info-hw_rev", &revision);
    of_node_put(root);
    if (ret || revision != 26)
        return -ENODEV;

    cover_bank = gpio_device_find_by_label("gpa3");
    if (!cover_bank)
        return -ENODEV;
    desc = gpio_device_get_desc(cover_bank, 6);
    if (IS_ERR(desc)) {
        ret = PTR_ERR(desc);
        goto put_bank;
    }
    cover_button.gpio = desc_to_gpio(desc);
    if (cover_button.gpio < 0) {
        ret = cover_button.gpio;
        goto put_bank;
    }
    cover_device = platform_device_register_data(NULL, "gpio-keys",
                         PLATFORM_DEVID_AUTO, &cover_keys, sizeof(cover_keys));
    if (IS_ERR(cover_device)) {
        ret = PTR_ERR(cover_device);
        goto put_bank;
    }
    return 0;

put_bank:
    gpio_device_put(cover_bank);
    return ret;
}

static void __exit cover_exit(void)
{
    platform_device_unregister(cover_device);
    gpio_device_put(cover_bank);
}

module_init(cover_init);
module_exit(cover_exit);
MODULE_DESCRIPTION("G965N rev26 active-low flip-cover GPIO keys device");
MODULE_LICENSE("GPL");

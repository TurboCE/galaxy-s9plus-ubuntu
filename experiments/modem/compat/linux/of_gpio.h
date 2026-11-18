/* SPDX-License-Identifier: GPL-2.0-only */
#pragma once
#include <linux/errno.h>
/* The reviewed modem tree uses mailbox IRQs and no integer GPIO properties. */
static inline int of_get_named_gpio(struct device_node *node, const char *name, int index)
{ return -ENOENT; }

/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef S9P_MAX77705_SOURCE_H
#define S9P_MAX77705_SOURCE_H
#ifdef __KERNEL__
#include <linux/types.h>
#else
#include <stddef.h>
#include <stdbool.h>
#endif

struct s9p_source_pdo {
 unsigned int index, current_ua, voltage_uv;
};

/* Samsung CURRENT_SRCCAP response: opcode, count/index, up to seven PDOs.
 * Only a complete selected fixed PDO is usable; advertisements alone are not.
 */
static inline bool s9p_source_pdo_parse(const unsigned char *reply, size_t length,
                                      struct s9p_source_pdo *out)
{
 unsigned int count, selected, offset, pdo;
 if (!reply || !out || length < 2 || reply[0] != 0x30)
  return false;
 count = reply[1] & 7;
 selected = (reply[1] >> 3) & 7;
 if (!selected || selected > count || length < 2 + count * 4)
  return false;
 offset = 2 + (selected - 1) * 4;
 pdo = (unsigned int)reply[offset] | (unsigned int)reply[offset + 1] << 8 |
       (unsigned int)reply[offset + 2] << 16 | (unsigned int)reply[offset + 3] << 24;
 if ((pdo >> 30) || !(pdo & 0x3ff) || !((pdo >> 10) & 0x3ff))
  return false;
 out->index = selected;
 out->current_ua = (pdo & 0x3ff) * 10000;
 out->voltage_uv = ((pdo >> 10) & 0x3ff) * 50000;
 return true;
}
#endif

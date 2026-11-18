#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply reviewed star2lte BCM4361 setup quirks to the pinned Linux source.

The stock board uses 3 Mbaud after firmware download. Its firmware also needs
the existing broken-LE-transmit-power quirk, otherwise setup rejects a short
command completion. ztOS documents these issues for the related starlte board;
this port deliberately scopes the adaptations to star2lte instead.
"""
from pathlib import Path
import sys


def replace_once(path, old, new):
    text = path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f"Kernel source changed; review Bluetooth anchor in {path.name}")
    text = text.replace(old, new)
    if '#include <linux/of.h>' not in text:
        anchor = '#include <linux/module.h>\n'
        if text.count(anchor) != 1:
            raise RuntimeError('Missing unique module include')
        text = text.replace(anchor, anchor + '#include <linux/of.h>\n')
    path.write_text(text)


def main():
    root = Path(sys.argv[1]) / 'drivers/bluetooth'
    replace_once(root / 'btbcm.c',
                 '\tif (dmi_first_match(disable_broken_read_transmit_power))\n',
                 '\tif (dmi_first_match(disable_broken_read_transmit_power) ||\n'
                 '\t    of_machine_is_compatible("samsung,star2lte"))\n')
    replace_once(root / 'hci_bcm.c',
                 '\telse if (hu->proto->oper_speed)\n\t\tspeed = hu->proto->oper_speed;\n\telse\n\t\tspeed = 0;\n\n\tif (speed) {\n\t\terr = bcm_set_baudrate(hu, speed);\n',
                 '\telse if (hu->proto->oper_speed)\n\t\tspeed = hu->proto->oper_speed;\n'
                 '\telse if (of_machine_is_compatible("samsung,star2lte"))\n\t\tspeed = 3000000;\n'
                 '\telse\n\t\tspeed = 0;\n\n\tif (speed) {\n\t\terr = bcm_set_baudrate(hu, speed);\n')


if __name__ == '__main__':
    main()

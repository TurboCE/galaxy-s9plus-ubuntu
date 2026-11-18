#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read Samsung stock BOOT's DTBH identifiers; never writes or flashes a device."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
from boot_parts import parts
from mkdtbh import root_props


def inspect(path):
    table = parts(Path(path).read_bytes())['dt']
    if table[:4] != b'DTBH' or len(table) < 12:
        raise ValueError('Stock boot image has no supported DTBH table.')
    version, count = struct.unpack_from('<II', table, 4)
    if version != 2 or count > 256 or 12 + count * 32 > len(table):
        raise ValueError('Invalid DTBH header.')
    rows = []
    for i in range(count):
        chip, platform, subtype, low, high, offset, size, _ = struct.unpack_from('<8I', table, 12 + 32 * i)
        if offset + size > len(table):
            raise ValueError('DTB extends past the image.')
        props = root_props(table[offset:offset + size])
        rows.append({'chip': hex(chip), 'platform': hex(platform), 'subtype': hex(subtype),
                     'revision_start': low, 'revision_end': high,
                     'model': props.get('model', b'').decode().rstrip('\0')})
    return rows


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('boot_backup', type=Path)
    args = p.parse_args()
    print(json.dumps(inspect(args.boot_backup), indent=2))

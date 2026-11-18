#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compare modem overlay properties to a private stock BOOT backup, without device IO."""
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/build'))
from boot_parts import parts

NODES = ('mif_pdata', 'shmem@F6E00000', 'mcu_ipc@14170000')


def tree(blob):
    if len(blob) < 40 or blob[:4] != b'\xd0\x0d\xfe\xed':
        raise ValueError('Invalid FDT')
    total, pos, strings = struct.unpack_from('>III', blob, 4)
    if total > len(blob):
        raise ValueError('Truncated FDT')
    stack, result = [], {}
    while pos + 4 <= total:
        token = struct.unpack_from('>I', blob, pos)[0]
        pos += 4
        if token == 1:
            end = blob.index(0, pos, total)
            stack.append(blob[pos:end].decode())
            pos = (end + 4) & ~3
            result['/'.join(stack)] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, name = struct.unpack_from('>II', blob, pos)
            pos += 8
            if pos + length > total:
                raise ValueError('Truncated property')
            name = blob[strings + name:blob.index(0, strings + name, total)].decode()
            result['/'.join(stack)][name] = blob[pos:pos + length]
            pos = (pos + length + 3) & ~3
        elif token == 4:
            continue
        elif token == 9:
            return result
        else:
            raise ValueError('Invalid FDT token')
    raise ValueError('Missing FDT end')


def stock_tree(path, revision):
    table = parts(Path(path).read_bytes())['dt']
    if table[:4] != b'DTBH':
        raise ValueError('Missing DTBH')
    version, count = struct.unpack_from('<II', table, 4)
    if version != 2 or count > 256 or 12 + count * 32 > len(table):
        raise ValueError('Invalid DTBH')
    matches = []
    for i in range(count):
        chip, _, _, low, high, offset, size, _ = struct.unpack_from('<8I', table, 12 + i * 32)
        if chip == 0x2652 and low <= revision <= high:
            if offset + size > len(table):
                raise ValueError('Truncated DTBH entry')
            matches.append(tree(table[offset:offset + size]))
    if len(matches) != 1:
        raise ValueError('Expected exactly one matching Star2 revision')
    return matches[0]


def subtree(nodes, prefix):
    return {path[len(prefix):]: {k: v for k, v in props.items()
            if k not in ('phandle', 'linux,phandle')}
            for path, props in nodes.items() if path == prefix or path.startswith(prefix + '/')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stock_boot', type=Path)
    p.add_argument('overlay', type=Path)
    p.add_argument('--revision', type=int, default=26)
    args = p.parse_args()
    stock, overlay = stock_tree(args.stock_boot, args.revision), tree(args.overlay.read_bytes())
    rows = []
    for node in NODES:
        a = subtree(stock, '/' + node)
        b = subtree(overlay, '/fragment@0/__overlay__/' + node)
        revision_ok = True
        if node == 'mif_pdata':
            # Legacy GPIO phandles belong to the stock tree, not mainline.
            # The adapted driver takes the observed revision explicitly.
            revision_ok = bool(a.get('', {}).get('gpios')) and 'gpios' not in b.get('', {})
            a.get('', {}).pop('gpios', None)
            expected = struct.pack('>I', args.revision)
            revision_ok = revision_ok and stock.get('', {}).get('model_info-hw_rev') == expected
            revision_ok = revision_ok and b.get('', {}).pop('samsung,hw-revision', None) == expected
        rows.append({'node': node, 'stock_children': len(a),
                     'explicit_revision_migration_valid': revision_ok,
                     'hardware_properties_match_after_revision_migration': bool(a) and a == b and revision_ok})
    print(json.dumps(rows, indent=2))
    if not all(row['hardware_properties_match_after_revision_migration'] for row in rows):
        raise SystemExit('Overlay differs from the stock handset; hardware probing remains blocked.')


if __name__ == '__main__':
    main()

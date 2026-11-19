#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only DT cache graph/geometry check against native42 measurements."""
import argparse
import json
import subprocess


def verify(dtb, tool='fdtget'):
    def cells(node, prop):
        text = subprocess.check_output([tool, '-t', 'u', str(dtb), node, prop], text=True)
        return [int(x) for x in text.split()]

    def one(node, prop):
        values = cells(node, prop)
        if len(values) != 1:
            raise ValueError('Expected one cell: ' + node + '/' + prop)
        return values[0]

    nodes = ['/l2-cache-a55', *['/l2-cache-m3-' + str(i) for i in range(4)], '/l3-cache-m3']
    handles = {one(node, 'phandle'): node for node in nodes}
    if len(handles) != 6:
        raise ValueError('Cache phandles must be distinct')
    observed = []
    for i, addr in enumerate(['0', '1', '2', '3', '100', '101', '102', '103']):
        cpu = '/cpus/cpu@' + addr
        expected = (32768, 64, 128, 32768, 64, 128) if i < 4 else (65536, 64, 128, 65536, 128, 128)
        props = ['d-cache-size', 'd-cache-line-size', 'd-cache-sets',
                 'i-cache-size', 'i-cache-line-size', 'i-cache-sets']
        if tuple(one(cpu, p) for p in props) != expected:
            raise ValueError('L1 geometry differs from measured CPU group')
        target = '/l2-cache-a55' if i < 4 else '/l2-cache-m3-' + str(i - 4)
        if handles.get(one(cpu, 'next-level-cache')) != target:
            raise ValueError('Wrong CPU private/shared cache edge')
        observed.append({'cpu': i, 'next': target})
    for node in nodes:
        expected = (3, 4194304, 64, 4096) if node == '/l3-cache-m3' else (2, 524288, 64, 512 if node == '/l2-cache-a55' else 1024)
        if tuple(one(node, p) for p in ['cache-level', 'cache-size', 'cache-line-size', 'cache-sets']) != expected:
            raise ValueError('Unified cache geometry mismatch')
        props = subprocess.check_output([tool, '-p', str(dtb), node], text=True).splitlines()
        if 'cache-unified' not in props:
            raise ValueError('Missing unified-cache description')
        if node.startswith('/l2-cache-m3-'):
            if handles.get(one(node, 'next-level-cache')) != '/l3-cache-m3':
                raise ValueError('Private M3 L2 must reach shared M3 L3')
        elif 'next-level-cache' in props:
            raise ValueError('Unexpected cache edge beyond measured hierarchy')
    return {'cache_nodes': len(nodes), 'cpu_edges': observed,
            'measured_geometry_matches': True, 'hardware_boot_qualified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dtb')
    parser.add_argument('--fdtget', default='fdtget')
    args = parser.parse_args()
    print(json.dumps(verify(args.dtb, args.fdtget)))

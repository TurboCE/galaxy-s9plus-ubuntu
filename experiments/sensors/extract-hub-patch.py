#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Extract the sensor-hub patch from an owner's private stock BOOT backup.

No downloads, device access or firmware redistribution. The stock kernel stores
the patch as a NUL-terminated ASCII record used by /dev/bbd_patch, not a raw ROM.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/build'))
from boot_parts import parts


def extract(kernel):
    marker = b'<FormatVersion=0x00010003>\n'
    if kernel.count(marker) != 1:
        raise ValueError('Expected one uncompressed stock hub-patch record')
    start = kernel.index(marker)
    end = kernel.find(b'\0', start)
    if end < 0 or end - start > 4 * 1024 * 1024:
        raise ValueError('Missing or oversized hub-patch terminator')
    record = kernel[start:end]
    length = re.search(rb'<BlobLength=(\d+)>', record)
    blob = re.search(rb'<Blob=([0-9A-Fa-f\r\n]+)>\n?$', record)
    if not length or not blob or b'<Name=bcm_sensorhub_a1>' not in record:
        raise ValueError('Unexpected hub-patch format or chip')
    payload = bytes.fromhex(blob[1].decode('ascii'))
    if len(payload) != int(length[1]):
        raise ValueError('Hub-patch payload length mismatch')
    return record + b'\0'  # sizeof the original C string included its terminator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_boot', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = extract(parts(args.stock_boot.read_bytes())['kernel'])
    os.umask(0o077)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(data)
    args.output.with_suffix('.json').write_text(json.dumps({
        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
        'source': 'owner stock BOOT backup; never redistribute this extracted file',
    }, indent=2) + '\n')
    print('Own-device sensor-hub patch extracted and structurally checked.')


if __name__ == '__main__':
    main()

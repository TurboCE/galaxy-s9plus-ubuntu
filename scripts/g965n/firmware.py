#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stage your own stock firmware locally; no network downloads or device writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = {'bcmdhd_sta.bin_b2': 'brcmfmac4361-pcie.bin',
         'nvram.txt_r02a_b2': 'brcmfmac4361-pcie.txt',
         'bcmdhd_clm.blob': 'brcmfmac4361-pcie.clm_blob'}


def stage(directory, root=ROOT):
    inputs = {name: (Path(directory) / name).read_bytes() for name in FILES}
    if any(not blob for blob in inputs.values()):
        raise ValueError('Empty firmware input')
    records = []
    for name, data in inputs.items():
        target = root / 'firmware' / name
        output = root / 'device/base/lib/firmware/brcm' / FILES[name]
        # Keep the original input unchanged. brcmfmac needs LF in its runtime
        # NVRAM text, matching the inherited kernel builder's normalization.
        runtime = data.replace(b'\r\n', b'\n') if name.startswith('nvram') else data
        for path, expected in ((target, data), (output, runtime)):
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.read_bytes() != expected:
                raise ValueError('Different firmware is already staged: ' + str(path))
        records.append({'file': name, 'sha256': hashlib.sha256(data).hexdigest()})
    for name, data in inputs.items():
        (root / 'firmware' / name).write_bytes(data)
        runtime = data.replace(b'\r\n', b'\n') if name.startswith('nvram') else data
        (root / 'device/base/lib/firmware/brcm' / FILES[name]).write_bytes(runtime)
    private = root / '.local'
    private.mkdir(mode=0o700, exist_ok=True)
    (private / 'firmware-inputs.json').write_text(json.dumps(records, indent=2) + '\n')
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, help='Own files with the three stock filenames')
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(stage(args.directory), indent=2))

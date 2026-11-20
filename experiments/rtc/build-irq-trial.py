#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build only: replace the reviewed RTC IRQ flags in a private #48 BOOT."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import struct
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'scripts/build'))
from boot_parts import parts
TREE = runpy.run_path(str(PROJECT / 'experiments/modem/verify-overlay.py'))['tree']


def fix_dtb(blob):
    before = TREE(blob)
    matches = [p for p, v in before.items()
               if v.get('compatible') == b'samsung,exynos8-rtc\0']
    if len(matches) != 1:
        raise ValueError('Expected one Exynos8 RTC')
    path = matches[0]
    original = struct.pack('>6I', 0, 31, 0, 0, 32, 0)
    corrected = struct.pack('>6I', 0, 31, 4, 0, 32, 4)
    if before[path].get('reg') != struct.pack('>2I', 0x141e0000, 0x100):
        raise ValueError('Unexpected RTC register resource')
    if before[path].get('interrupts') != original or blob.count(original) != 1:
        raise ValueError('Unknown or ambiguous RTC interrupt metadata')
    result = blob.replace(original, corrected, 1)
    expected = {p: dict(v) for p, v in before.items()}
    expected[path]['interrupts'] = corrected
    if TREE(result) != expected or sum(a != b for a, b in zip(blob, result)) != 2:
        raise ValueError('DTB changed beyond the two RTC flag bytes')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot', type=Path, required=True)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.boot.read_bytes()
    original = parts(raw)
    dtb = args.dtb.read_bytes()
    corrected = fix_dtb(dtb)
    if original['kernel'].count(dtb) != 1 or original['second']:
        raise ValueError('Expected exactly one inner DTB and no second stage')
    wrapper = original['kernel'].replace(dtb, corrected, 1)
    args.output.mkdir(mode=0o700)
    (args.output / 'wrapper').write_bytes(wrapper)
    (args.output / 'rtc-irq.dtb').write_bytes(corrected)
    (args.output / 'outer-dt.img').write_bytes(original['dt'])
    image = args.output / 'boot-rtc-irq.img'
    subprocess.run([sys.executable, str(PROJECT / 'scripts/build/mkboot.py'),
                    '--ref', str(args.boot), '--kernel', str(args.output / 'wrapper'),
                    '--dt', str(args.output / 'outer-dt.img'), '-o', str(image)], check=True)
    final = parts(image.read_bytes())
    if final['kernel'] != wrapper or any(final[k] != original[k] for k in ('dt', 'ramdisk', 'second')):
        raise ValueError('BOOT packaging changed an unrelated component')
    sha = lambda b: hashlib.sha256(b).hexdigest()
    receipt = {'scope': 'RTC IRQ31/32 NONE to LEVEL_HIGH, no device writes',
               'base_boot_sha256': sha(raw), 'boot_sha256': sha(image.read_bytes()),
               'dtb_before_sha256': sha(dtb), 'dtb_after_sha256': sha(corrected),
               'wrapper_changed_bytes': sum(a != b for a, b in zip(original['kernel'], wrapper)),
               'hardware_validation': 'pending'}
    (args.output / 'build.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Built and unpacked the RTC-only BOOT candidate; hardware validation pending')


if __name__ == '__main__':
    main()

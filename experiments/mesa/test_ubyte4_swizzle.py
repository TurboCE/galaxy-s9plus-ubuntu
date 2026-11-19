#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply the pinned Mesa patch privately and test its actual NEON helper on ARM64."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
TARGET = Path('src/mesa/main/format_utils.c')
PATCH = HERE / '0002-mesa-neon-ubyte4-swizzle.patch'
BASE_SHA = '43db67a2f1e33f38931bb4be82506689c000651c0f6d986e457ed5ca98d8405c'
PATCHED_SHA = '1d8367b70698a89f47f64201021591cc38db450a1d1364cb0cd5fdd1c8a5288f'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesa-source', required=True, type=Path)
    args = parser.parse_args()
    if platform.machine().lower() not in ('aarch64', 'arm64'):
        parser.error('An ARM64 host is required to execute the NEON regression')
    source = args.mesa_source / TARGET
    if digest(source) != BASE_SHA:
        raise ValueError('Expected unmodified Mesa 25.2.8 format_utils.c')

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / TARGET
        target.parent.mkdir(parents=True)
        shutil.copyfile(source, target)
        with PATCH.open('rb') as patch:
            subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1'],
                           cwd=root, stdin=patch, check=True)
        if digest(target) != PATCHED_SHA:
            raise ValueError('Patched Mesa source differs from the tested source')
        text = target.read_text()
        start = text.index('static bool\nswizzle_convert_ubyte4_neon(')
        end = text.index('#endif', start)
        case = root / 'check.c'
        case.write_text('#include <arm_neon.h>\n#include <stdbool.h>\n#include <stdint.h>\n'
                        + text[start:end] + (HERE / 'test_ubyte4_swizzle.c').read_text())
        binary = root / 'check'
        subprocess.run([os.getenv('CC', 'cc'), '-O2', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', str(case), '-o', str(binary)],
                       check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()

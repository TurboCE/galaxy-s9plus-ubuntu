#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply reviewed source patches only; never build, enable, or access hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def checksum(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Expected ordinary pinned source: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source):
    source = source.resolve(strict=True)
    manifest = json.loads((HERE / 'SOURCES.json').read_text())
    pending = []
    for entry in manifest['files']:
        patch = HERE / entry['patch']
        if checksum(patch) != entry['patch_sha256']:
            raise RuntimeError('Reviewed patch hash changed')
        target = source / entry['path']
        if not target.resolve().is_relative_to(source):
            raise RuntimeError('Source path escapes kernel tree')
        actual = checksum(target)
        if actual == entry['after_sha256']:
            continue
        if actual != entry['before_sha256']:
            raise RuntimeError('Unreviewed source drift: ' + entry['path'])
        pending.append(entry)
    return source, pending


def apply(source, check=False):
    source, pending = prepare(source)
    for entry in pending:
        subprocess.run(['patch', '--dry-run', '--batch', '--forward', '--fuzz=0', '-p1',
                        '-i', str(HERE / entry['patch'])], cwd=source, check=True)
    if not check:
        for entry in pending:
            subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1',
                            '-i', str(HERE / entry['patch'])], cwd=source, check=True)
            if checksum(source / entry['path']) != entry['after_sha256']:
                raise RuntimeError('Patch output mismatch; preserve the tree for review')
    return len(pending)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'apply'])
    parser.add_argument('--kernel-source', type=Path, required=True)
    args = parser.parse_args()
    try:
        print('Pending source patches:', apply(args.kernel_source, args.action == 'check'))
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))

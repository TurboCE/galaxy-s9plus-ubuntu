#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit, isolated EFS-superblock provenance maintenance; never writes EFS.

Keeps the original bounded proof in vendor-runtime.py. This wrapper prepares
the read-only private view that the legacy maintenance command requires.
It never starts a modem daemon, deletes an attempt marker or restarts a service.
"""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat


def maintain(runtime, args):
    """Keep both exclusive leases through preparation, proof and cleanup."""
    runtime.select_modem_runtime()
    runtime.assert_board()
    with runtime.checked_lock(runtime.STATE_LOCK, runtime.fcntl.LOCK_EX), \
            runtime.checked_lock(runtime.RUNTIME_LOCK, runtime.fcntl.LOCK_EX):
        runtime.assert_modem_stopped()
        if runtime.ROOT.is_mount():
            raise RuntimeError('Existing modem runtime preserved; maintenance refused')
        try:
            runtime.prepare(create_devices=False)
            runtime.revalidate_efs_superblock(
                args.old_efs_backup, args.efs_backup, args.cpefs_backup,
                args.backup_manifest, confirm=True)
        finally:
            runtime.teardown()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime', type=Path, required=True)
    p.add_argument('--runtime-sha256', required=True)
    p.add_argument('--old-efs-backup', type=Path, required=True)
    p.add_argument('--efs-backup', type=Path, required=True)
    p.add_argument('--cpefs-backup', type=Path, required=True)
    p.add_argument('--backup-manifest', type=Path, required=True)
    p.add_argument('--confirm-sm-g965n-efs-metadata-only', action='store_true', required=True)
    args = p.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Run on the checked handset as root')
    os.umask(0o077)
    path = args.runtime
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise RuntimeError('Runtime must be an absolute canonical path')
    for component in (path, *path.parents):
        info = component.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('Runtime and ancestors must be root-owned and protected')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError('Expected a regular protected runtime source')
    if (not re.fullmatch('[0-9a-f]{64}', args.runtime_sha256) or
            hashlib.sha256(path.read_bytes()).hexdigest() != args.runtime_sha256):
        raise RuntimeError('Runtime source pin mismatch')
    spec = importlib.util.spec_from_file_location('checked_runtime', path)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    maintain(runtime, args)


if __name__ == '__main__':
    main()

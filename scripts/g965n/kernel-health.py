#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded read-only hardware inspection; raw boot logs stay root-private.

A clean journal is insufficient when it has not retained the early kernel log.
No resets, clocks, module changes, partition writes, or log clearing.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess

COMMANDS = {
    'ring': ['dmesg', '--color=never'],
    'ring-errors': ['dmesg', '--color=never', '--level=emerg,alert,crit,err'],
    'ring-warnings': ['dmesg', '--color=never', '--level=warn'],
    'journal': ['journalctl', '-k', '-b', '--no-pager', '-o', 'cat'],
    'journal-errors': ['journalctl', '-k', '-b', '-p', 'err', '--no-pager', '-o', 'cat'],
}
PATTERNS = {
    'cpu_register_variations': r'Unexpected variation in ',
    'unsupported_cpu_variation': r'Unsupported CPU feature variation',
    'hub_reset_unconfirmed': r'MCU_RESP still high',
    'hub_standby_observations': r'hub held [0-9]+ ms:',
    'pmic_firmware_failures': r'PMIC firmware failure',
    'action_frame_retry_failures': r'Failed to send Action Frame',
    'chanspec_failures': r'chanspec failed',
    'call_traces': r'Call trace:',
    'serror_mentions': r'\bSError\b',
}


def summary(logs):
    ring, journal = logs['ring'], logs['journal']
    return {
        'ring_boot_header_present': 'Linux version ' in ring,
        'journal_boot_header_present': 'Linux version ' in journal,
        'journal_early_boot_missing': 'Linux version ' in ring and 'Linux version ' not in journal,
        'ring_lines': len(ring.splitlines()), 'journal_lines': len(journal.splitlines()),
        'ring_error_priority_lines': len(logs['ring-errors'].splitlines()),
        'ring_warning_priority_lines': len(logs['ring-warnings'].splitlines()),
        'journal_error_priority_lines': len(logs['journal-errors'].splitlines()),
        'known_message_counts': {name: len(re.findall(pattern, ring)) for name, pattern in PATTERNS.items()},
        'all_hardware_qualified': False,
    }


def write_private(path, data):
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('Output parent must be owned and private0700')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def collect(directory):
    logs = {}
    # Sequential collection is an observation window, not an atomic snapshot.
    for name, command in COMMANDS.items():
        result = subprocess.run(command, check=True, text=True, capture_output=True, timeout=15)
        logs[name] = result.stdout
        write_private(directory / (name + '-private.txt'), result.stdout)
    result = summary(logs)
    write_private(directory / 'summary.json', json.dumps(result, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=['SM-G965N'], required=True)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--receipt-sha256', required=True)
    p.add_argument('--backup', type=Path, required=True)
    p.add_argument('--backup-sha256', required=True)
    p.add_argument('--confirm-backup-verified', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if os.geteuid() != 0 or not args.confirm_backup_verified:
        p.error('Root and explicit verified backup required')
    helper = Path(__file__).with_name('p2p-control-trial.py')
    spec = importlib.util.spec_from_file_location('kernel_guard', helper)
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    guard.validate(guard.trusted_json(args.receipt, args.receipt_sha256),
                   guard.trusted_json(args.backup, args.backup_sha256), require_off=False)
    guard.protected_parent(args.output)
    args.output.mkdir(mode=0o700)  # Never overwrite an earlier observation.
    print(json.dumps(collect(args.output)), flush=True)


if __name__ == '__main__':
    main()

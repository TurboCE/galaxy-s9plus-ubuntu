#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Audit or explicitly repair only an empty secondary GPT on the checked G965N.

This is a device maintenance tool, not part of any image build. Never prints
partition names, GUIDs or handset identifiers. Private snapshots are mandatory.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import zlib


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_report(path, report):
    with path.open('w') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def plan(primary, tail, sector, size):
    """Validate a complete primary GPT; derive only its missing backup copy."""
    require(sector in (512, 4096) and size % sector == 0, 'Invalid geometry')
    require(len(primary) == sector * 6 and len(tail) == sector * 6, 'Incomplete metadata snapshot')
    header = primary[sector:sector * 2]
    require(header[:8] == b'EFI PART', 'Missing primary GPT')
    revision, length, checksum, reserved = struct.unpack_from('<4I', header, 8)
    require(revision == 0x10000 and length in (92, 512) and reserved == 0, 'Unsupported GPT header')
    # This Samsung primary uses a CRC over 512 bytes, including its zero
    # extension. Preserve that size and include it in the backup CRC too.
    require(not any(header[92:length]), 'Unknown GPT header extension')
    checked = bytearray(header[:length])
    struct.pack_into('<I', checked, 16, 0)
    require(zlib.crc32(checked) == checksum, 'Primary GPT header CRC mismatch')
    current, alternate, first, last = struct.unpack_from('<4Q', header, 24)
    table_lba, count, width, table_crc = struct.unpack_from('<QIII', header, 72)
    require(current == 1 and alternate == size // sector - 1, 'Unexpected GPT locations')
    require(table_lba == 2 and count == 128 and width == 128, 'Unexpected partition array')
    array_bytes = count * width
    blocks = (array_bytes + sector - 1) // sector
    require(2 + blocks <= 6, 'Primary snapshot is too small')
    backup_lba = alternate - blocks
    require(first >= 2 + blocks and first <= last < backup_lba, 'Usable range overlaps metadata')
    array = primary[table_lba * sector:table_lba * sector + array_bytes]
    require(zlib.crc32(array) == table_crc, 'Primary partition array CRC mismatch')
    ranges = []
    for i in range(count):
        entry = array[i * width:(i + 1) * width]
        if entry[:16] == bytes(16):
            continue
        start, end = struct.unpack_from('<2Q', entry, 32)
        require(first <= start <= end <= last, 'Partition outside usable range')
        ranges.append((start, end))
    require(bool(ranges), 'Empty partition table')
    ranges.sort()
    require(all(a[1] < b[0] for a, b in zip(ranges, ranges[1:])), 'Overlapping partitions')
    require(blocks + 1 <= 6, 'Secondary snapshot is too small')
    old = tail[-(blocks + 1) * sector:]
    require(not any(old), 'Secondary metadata is not empty; manual review required')
    backup = bytearray(sector)
    backup[:length] = header[:length]
    struct.pack_into('<2Q', backup, 24, alternate, current)
    struct.pack_into('<Q', backup, 72, backup_lba)
    struct.pack_into('<I', backup, 16, 0)
    struct.pack_into('<I', backup, 16, zlib.crc32(backup[:length]))
    payload = array.ljust(blocks * sector, b'\0') + backup
    return backup_lba * sector, payload, len(ranges)


def verify_device(manifest_path, profile_root):
    require(os.geteuid() == 0, 'Root required for device maintenance')
    require(os.uname().version.startswith('#48 '), 'Expected reviewed native #48 trial')
    backup = json.loads(manifest_path.read_bytes())
    receipt = json.loads((profile_root / 'startup.json').read_bytes())
    require(backup.get('complete') is True and backup.get('model') == 'SM-G965N', 'Wrong or incomplete backup')
    require(backup['bootloader'].startswith('G965N'), 'Wrong backup model')
    entries = {e['name']: e for e in backup['partitions']}
    require(len(backup['partitions']) == 9 and
            set(entries) == {'BOOT', 'DTB', 'DTBO', 'EFS', 'CPEFS', 'RADIO', 'MISC', 'RECOVERY', 'PARAM'}, 'Incomplete backup set')
    require(receipt['model'] == 'SM-G965N' and receipt['kernel_version'] == os.uname().version,
            'Service receipt model/kernel mismatch')
    require(receipt['kernel_release'] == os.uname().release, 'Kernel release mismatch')
    require((profile_root / 'backup.json').read_bytes() == manifest_path.read_bytes(), 'Backup receipt mismatch')
    with open('/dev/sda10', 'rb') as stream:
        require(sha(stream.read(receipt['boot_bytes'])) == receipt['boot_sha256'], 'Live BOOT mismatch')
    for name, node in {'RECOVERY':'sda11', 'EFS':'sda3', 'CPEFS':'sdd1', 'RADIO':'sda12', 'DTB':'sda8', 'DTBO':'sda9'}.items():
        result = subprocess.check_output(['sha256sum', '/dev/' + node], text=True).split()[0]
        require(result == entries[name]['sha256'], 'Protected partition changed: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True, help='New root-private metadata backup directory')
    parser.add_argument('--apply-sm-g965n-secondary-only', action='store_true', help='Explicit device-write consent')
    parser.add_argument('--backup-manifest', type=Path)
    parser.add_argument('--profile-root', type=Path)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Root required for metadata snapshot')
    sector = int(Path('/sys/class/block/sda/queue/logical_block_size').read_text())
    size = int(Path('/sys/class/block/sda/size').read_text()) * 512
    require(sector == 4096, 'Unqualified handset geometry')
    if args.apply_sm_g965n_secondary_only:
        require(args.backup_manifest and args.profile_root, 'Backup and model/BOOT receipt required')
        verify_device(args.backup_manifest, args.profile_root)
    os.umask(0o077)
    args.snapshot.mkdir(mode=0o700)  # Existing/partial snapshots are never overwritten.
    flags = os.O_RDWR if args.apply_sm_g965n_secondary_only else os.O_RDONLY
    fd = os.open('/dev/sda', flags)
    try:
        require(stat.S_ISBLK(os.fstat(fd).st_mode), 'Expected native block device')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        primary = os.pread(fd, 6 * sector, 0)
        tail = os.pread(fd, 6 * sector, size - 6 * sector)
        offset, payload, partitions = plan(primary, tail, sector, size)
        for name, data in [('primary.bin', primary), ('tail.bin', tail), ('candidate.bin', payload)]:
            with (args.snapshot / name).open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        report = dict(sector=sector, disk_bytes=size, offset=offset, bytes=len(payload),
                      partitions=partitions, primary_sha256=sha(primary), tail_sha256=sha(tail),
                      candidate_sha256=sha(payload), applied=False)
        record = args.snapshot / 'receipt.json'
        save_report(record, report)
        syncdir = os.open(args.snapshot, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(syncdir)
        finally:
            os.close(syncdir)
        require(os.pread(fd, len(primary), 0) == primary and
                os.pread(fd, len(tail), size - len(tail)) == tail, 'Metadata changed during preparation')
        if args.apply_sm_g965n_secondary_only:
            # Write only the empty reserved backup array/header, never primary
            # metadata or any partition. Do not request an online partition rescan.
            require(os.pwrite(fd, payload, offset) == len(payload), 'Short secondary GPT write; retained private snapshot')
            os.fsync(fd)
            require(os.pread(fd, len(payload), offset) == payload, 'Secondary GPT readback mismatch')
            require(os.pread(fd, len(primary), 0) == primary, 'Primary metadata changed')
            verify_device(args.backup_manifest, args.profile_root)
            report['applied'] = True
            save_report(record, report)
        print(json.dumps({'primary_valid': True, 'partitions': partitions,
                          'secondary_bytes': len(payload), 'applied': report['applied']}))
    finally:
        os.close(fd)


if __name__ == '__main__':
    main()

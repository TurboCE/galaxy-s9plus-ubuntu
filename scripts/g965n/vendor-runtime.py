#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare an isolated filesystem for the owner's stock vendor programs.

Run manually as root on native Ubuntu. Does not start Android, lhd or cbd.
SYSTEM/VENDOR are read-only with no journal replay; identity/radio partitions
are never mounted or exposed as block devices inside this runtime.
"""
import argparse
import copy
import fcntl
import hashlib
import json
import re
import time
import os
from pathlib import Path
import stat
import subprocess
import shutil
import struct
import tempfile
from contextlib import contextmanager

BASE = Path('/run/g965n-vendor-runtime')
ROOT = BASE / 'root'
DATA = Path('/var/lib/g965n-vendor-runtime/data')
STATE = DATA.parent

ROOT_UID = 0
RECEIPT_NAME = 'modem-provenance.json'
BACKUP_PARTITIONS = {'BOOT', 'DTB', 'DTBO', 'EFS', 'CPEFS', 'RADIO', 'MISC', 'RECOVERY', 'PARAM'}
SALT = b'Samsung_Android_RIL'
COMPATIBLE = Path('/sys/firmware/devicetree/base/compatible')
MOUNTINFO = Path('/proc/self/mountinfo')
PARTITION_SPECS = {
    'EFS': (Path('/dev/sda3'), 20971520),
    'CPEFS': (Path('/dev/sdd1'), 6291456),
    'RADIO': (Path('/dev/sda12'), 52428800),
}


STATE_LOCK = Path('/run/g965n-vendor-runtime.lock')
RUNTIME_LOCK = STATE_LOCK
SENSOR_BASE = Path('/run/g965n-sensor-runtime')
MODEM_BASE = Path('/run/g965n-modem-runtime')


def select_sensor_runtime():
    """Select a sensor-only mount tree and lease independent of modem NV."""
    global BASE, ROOT, DATA, RUNTIME_LOCK
    BASE = SENSOR_BASE
    ROOT = BASE / 'root'
    DATA = STATE / 'sensor-data'
    RUNTIME_LOCK = Path('/run/g965n-sensor-runtime.lock')


def select_modem_runtime():
    """Select the fixed modem view before opening any leases or mounts."""
    global BASE, ROOT, DATA, RUNTIME_LOCK
    BASE = MODEM_BASE
    ROOT = BASE / 'root'
    DATA = STATE / 'modem-data'
    RUNTIME_LOCK = Path('/run/g965n-modem-runtime.lock')


def runtime_lock_paths():
    return (STATE_LOCK,) if RUNTIME_LOCK == STATE_LOCK else (STATE_LOCK, RUNTIME_LOCK)


@contextmanager
def checked_lock(path, mode):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with open(fd, 'rb', closefd=True):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                info.st_uid != ROOT_UID or stat.S_IMODE(info.st_mode) & 0o077):
            raise RuntimeError('Unexpected runtime lock file')
        fcntl.flock(fd, mode | fcntl.LOCK_NB)
        yield fd


@contextmanager
def shared_runtime_lock():
    """Keep the private NV and selected runtime view stable through I/O."""
    with checked_lock(STATE_LOCK, fcntl.LOCK_SH) as state_fd:
        if RUNTIME_LOCK == STATE_LOCK:
            yield state_fd
        else:
            with checked_lock(RUNTIME_LOCK, fcntl.LOCK_SH) as runtime_fd:
                yield runtime_fd


@contextmanager
def modem_runtime_setup_lock():
    """Allow sensor readers while changing only the isolated modem view."""
    if BASE != MODEM_BASE:
        raise RuntimeError('Select the isolated modem runtime first')
    with checked_lock(STATE_LOCK, fcntl.LOCK_SH):
        with checked_lock(RUNTIME_LOCK, fcntl.LOCK_EX):
            yield


def verify_private_bindings():
    """Call under shared lease after provenance/NV verification, before CP I/O."""
    safe_components(DATA)
    if not os.path.ismount(ROOT):
        raise RuntimeError('Private vendor runtime is not mounted')
    for name in ('system', 'vendor'):
        path = ROOT / name
        safe_components(path)
        if not os.path.ismount(path) or not os.statvfs(path).f_flag & os.ST_RDONLY:
            raise RuntimeError('Stock runtime files must remain read-only')
    for name in ('efs', 'cpefs'):
        target = ROOT / 'mnt/vendor' / name
        safe_components(target)
        if not os.path.ismount(target) or not os.path.samefile(target, STATE / name):
            raise RuntimeError('Runtime NV is not the validated private copy')
    radio = ROOT / 'dev/block/platform/11120000.ufs/by-name/RADIO'
    regular_info(radio)
    if (not os.path.ismount(radio) or not os.path.samefile(radio, STATE / 'RADIO') or
            not os.statvfs(radio).f_flag & os.ST_RDONLY):
        raise RuntimeError('Runtime RADIO must be the read-only validated regular copy')


def assert_board():
    if b'samsung,star2lte' not in COMPATIBLE.read_bytes().split(b'\0'):
        raise RuntimeError('Expected native star2lte')


def safe_components(path, missing_leaf=False):
    """No symlink or non-directory ancestor, including dangling symlinks."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise RuntimeError('Expected an absolute private path')
    current = Path(path.anchor)
    for index, part in enumerate(path.parts[1:]):
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if missing_leaf and index == len(path.parts)-2:
                return
            raise RuntimeError('Missing private path component') from None
        if stat.S_ISLNK(info.st_mode):
            raise RuntimeError('Symlink in private path')
        if current != path and not stat.S_ISDIR(info.st_mode):
            raise RuntimeError('Non-directory private path ancestor')


def regular_info(path, size=None, maximum=None):
    safe_components(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RuntimeError('Expected a single-link regular private file')
    if size is not None and info.st_size != size:
        raise RuntimeError('Unexpected private file size')
    if maximum is not None and not 0 < info.st_size <= maximum:
        raise RuntimeError('Private file exceeds its bound')
    return info


def read_regular(path, maximum):
    regular_info(path, maximum=maximum)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with open(fd, 'rb', closefd=True) as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise RuntimeError('Regular input changed type')
        data = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        if (not 0 < len(data) <= maximum or len(data) != before.st_size or
                (before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_ino, after.st_size, after.st_mtime_ns)):
            raise RuntimeError('Regular input changed during verification')
        return data


def digest(path, size=None):
    """Read only, with no-follow leaf open and stable-file checks."""
    with open(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb', closefd=True) as stream:
        before = os.fstat(stream.fileno())
        if size is not None and stat.S_ISREG(before.st_mode) and before.st_size != size:
            raise RuntimeError('Unexpected input size')
        result = hashlib.sha256()
        count = 0
        while chunk := stream.read(1024 * 1024):
            result.update(chunk); count += len(chunk)
        after = os.fstat(stream.fileno())
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise RuntimeError('Input changed during verification')
        if size is not None and count != size:
            raise RuntimeError('Short input read')
        return result.hexdigest()


@contextmanager
def verified_backup_snapshot(image, expected):
    """Extract only an immutable-to-unprivileged-users copy of verified input."""
    regular_info(image, size=expected['bytes'])
    with tempfile.TemporaryDirectory(prefix='.verified-backup-', dir=STATE) as directory:
        os.chmod(directory, 0o700)
        snapshot = Path(directory) / 'partition.img'
        fd = os.open(image, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with open(fd, 'rb', closefd=True) as source, snapshot.open('xb') as output:
            before = os.fstat(source.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or
                    before.st_size != expected['bytes']):
                raise RuntimeError('Backup changed before snapshot')
            remaining = expected['bytes']
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise RuntimeError('Short backup snapshot')
                output.write(chunk); remaining -= len(chunk)
            after = os.fstat(source.fileno())
            if (source.read(1) or
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) !=
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                raise RuntimeError('Backup changed during snapshot')
            output.flush(); os.fsync(output.fileno())
        snapshot.chmod(0o400)
        if digest(snapshot, expected['bytes']) != expected['sha256']:
            raise RuntimeError('Backup snapshot checksum mismatch')
        yield snapshot


def file_inventory(path, maximum=None):
    info = regular_info(path, maximum=maximum)
    return {'bytes': info.st_size, 'sha256': digest(path, info.st_size),
            'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid,
            'gid': info.st_gid, 'mtime_ns': info.st_mtime_ns}


def private_permissions(path, uid, gid, directory_mode, file_mode=None):
    """Walk relative to verified no-follow directory FDs, never follow a link."""
    safe_components(path)
    def update(fd):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode):
            for name in os.listdir(fd):
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    update(child)
                finally:
                    os.close(child)
            os.fchown(fd, uid, gid); os.fchmod(fd, directory_mode)
        elif file_mode is not None and stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            os.fchown(fd, uid, gid); os.fchmod(fd, file_mode)
        else:
            raise RuntimeError('Unexpected private permission target')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        update(fd)
    finally:
        os.close(fd)


def private_state():
    safe_components(STATE)
    info = STATE.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != ROOT_UID or
            stat.S_IMODE(info.st_mode) & 0o077):
        raise RuntimeError('State directory must be private and root-owned')


def tree_inventory(directory, maximum_bytes=128 * 1024 * 1024):
    """NV copies may contain directories and ordinary files, never host links/devices."""
    safe_components(directory)
    if not stat.S_ISDIR(directory.lstat().st_mode):
        raise RuntimeError('Expected a private NV directory')
    entries = []
    total_bytes = 0
    for root, dirs, files in os.walk(directory, followlinks=False):
        for name in ['.'] + sorted(dirs + files):
            path = Path(root) if name == '.' else Path(root) / name
            info = path.lstat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise RuntimeError('NV symlinks and special files are forbidden')
            entry = {'path': str(path.relative_to(directory)), 'mode': stat.S_IMODE(info.st_mode),
                     'uid': info.st_uid, 'gid': info.st_gid, 'mtime_ns': info.st_mtime_ns,
                     'kind': 'directory' if stat.S_ISDIR(info.st_mode) else 'file'}
            if stat.S_ISREG(info.st_mode):
                total_bytes += info.st_size
                if total_bytes > maximum_bytes:
                    raise RuntimeError('Private NV tree exceeds its partition bound')
                regular_info(path)
                entry.update(bytes=info.st_size, sha256=digest(path, info.st_size))
            entries.append(entry)
            if len(entries) > 20000:
                raise RuntimeError('Unexpectedly large NV directory tree')
    # os.walk reports directories both from their parent and as its current root.
    return sorted({e['path']: e for e in entries}.values(), key=lambda e: e['path'])


def archive_tree_inventory(directory, maximum_bytes=128 * 1024 * 1024):
    """Opaque preservation only: never follow links or open special inodes."""
    safe_components(directory)
    if not stat.S_ISDIR(directory.lstat().st_mode):
        raise RuntimeError('Archive root must be an actual directory')
    entries = {}
    total = 0
    for root, dirs, files, parent_fd in os.fwalk(directory, follow_symlinks=False):
        relative_root = Path(root).relative_to(directory)
        if len(relative_root.parts) > 32:
            raise RuntimeError('Legacy archive tree exceeds depth bound')
        for name in ['.'] + sorted(dirs + files):
            info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            relative = relative_root if name == '.' else relative_root / name
            row = {'path': str(relative), 'mode': info.st_mode, 'uid': info.st_uid,
                   'gid': info.st_gid, 'mtime_ns': info.st_mtime_ns,
                   'nlink': info.st_nlink, 'inode': info.st_ino, 'device': info.st_dev}
            if stat.S_ISREG(info.st_mode):
                if info.st_nlink != 1:
                    raise RuntimeError('Legacy archive regular hardlinks require manual review')
                total += info.st_size
                if total > maximum_bytes:
                    raise RuntimeError('Legacy archive tree exceeds byte bound')
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
                with open(fd, 'rb', closefd=True) as stream:
                    before = os.fstat(stream.fileno())
                    if (before.st_dev, before.st_ino, before.st_mode, before.st_size) != (
                            info.st_dev, info.st_ino, info.st_mode, info.st_size):
                        raise RuntimeError('Legacy archive file changed before read')
                    checksum = hashlib.sha256(); count = 0
                    while chunk := stream.read(min(1024 * 1024, info.st_size - count + 1)):
                        count += len(chunk)
                        if count > info.st_size:
                            raise RuntimeError('Legacy archive file grew during read')
                        checksum.update(chunk)
                    after = os.fstat(stream.fileno())
                    if count != info.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise RuntimeError('Legacy archive file changed during read')
                row.update(kind='file', bytes=info.st_size, sha256=checksum.hexdigest())
            elif stat.S_ISLNK(info.st_mode):
                link = os.fsencode(os.readlink(name, dir_fd=parent_fd))
                if len(link) > 4096:
                    raise RuntimeError('Legacy archive link exceeds bound')
                row.update(kind='symlink', bytes=len(link), link_sha256=hashlib.sha256(link).hexdigest())
            elif stat.S_ISDIR(info.st_mode):
                row['kind'] = 'directory'
            else:
                # Sockets, FIFO and device nodes are described, never opened.
                row.update(kind='special', rdev=info.st_rdev)
            entries[str(relative)] = row
            if len(entries) > 20000:
                raise RuntimeError('Legacy archive tree exceeds entry bound')
    return sorted(entries.values(), key=lambda row: row['path'])


def copy_ordinary_extraction(source, destination, inventory, excluded):
    """Copy regular bytes from root-private quarantine, never dereference links."""
    destination.mkdir(mode=0o700)
    for row in inventory:
        relative = row['path']
        if relative == '.' or relative in excluded:
            continue
        target = destination / relative
        if row['kind'] == 'directory':
            target.mkdir(mode=0o700)
        elif row['kind'] == 'file':
            original = source / relative
            regular_info(original, size=row['bytes'])
            with open(os.open(original, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb', closefd=True) as src, target.open('xb') as dst:
                remaining = row['bytes']; checksum = hashlib.sha256()
                while remaining:
                    chunk = src.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise RuntimeError('Short quarantined extraction read')
                    checksum.update(chunk); dst.write(chunk); remaining -= len(chunk)
                if src.read(1) or checksum.hexdigest() != row['sha256']:
                    raise RuntimeError('Quarantined extraction changed during copy')
                dst.flush(); os.fsync(dst.fileno())
            target.chmod(0o600)
        else:
            raise RuntimeError('Only ordinary working files may leave quarantine')


def prepare_quarantined_extractions(efs, cpefs, receipt):
    """Preserve complete verified input; exclude only the stock diagnostic link."""
    quarantine = STATE / ('quarantine-' + str(time.time_ns()))
    quarantine.mkdir(mode=0o700)
    inventories = {}; excluded = []
    for name, image in [('efs', efs), ('cpefs', cpefs)]:
        raw = quarantine / name
        raw.mkdir(mode=0o700)
        with verified_backup_snapshot(image, receipt['source'][name.upper()]) as snapshot:
            assert_modem_stopped()
            run('debugfs', '-R', 'rdump / ' + str(raw), snapshot)
        rows = archive_tree_inventory(raw, receipt['source'][name.upper()]['bytes'])
        inventories[name] = rows
    # Classify before creating either working clone. Unknown links/specials stop
    # staging while preserving the complete extracted source for investigation.
    for name, rows in inventories.items():
        for row in rows:
            if row['kind'] in ('directory', 'file'):
                continue
            if name == 'efs' and row['path'] == 'cpdebug/node' and row['kind'] == 'symlink':
                excluded.append({'partition': 'EFS', 'path': row['path'],
                                 'link_sha256': row['link_sha256'],
                                 'source_backup_sha256': receipt['source']['EFS']['sha256']})
            else:
                raise RuntimeError('Unreviewed link/special inode in source extraction; preserved in quarantine')
    provenance = {'schema': 1, 'purpose': 'complete-source-preserved-not-bound',
                  'source': receipt['source'], 'inventory': inventories, 'excluded': excluded}
    write_private_json(quarantine / 'extraction-inventory.json', provenance)
    for name, rows in inventories.items():
        copy_ordinary_extraction(quarantine / name, STATE / name, rows,
                                 {'cpdebug/node'} if name == 'efs' and excluded else set())
        if archive_tree_inventory(quarantine / name, receipt['source'][name.upper()]['bytes']) != rows:
            raise RuntimeError('Quarantined source changed; preserve all copies for review')
        tree_inventory(STATE / name, receipt['source'][name.upper()]['bytes'])
    receipt['extraction'] = {'quarantine': str(quarantine), 'excluded': excluded,
                             'inventory_sha256': digest(quarantine / 'extraction-inventory.json')}


def verify_nv(directory, expected_size=None):
    data = directory / 'nv_data.bin'
    checksum = directory / 'nv_data.bin.md5'
    info = regular_info(data, size=expected_size, maximum=16 * 1024 * 1024)
    regular_info(checksum, maximum=128)
    value = read_regular(checksum, 128).decode('ascii').strip().lower()
    if not re.fullmatch(r'[0-9a-f]{32}', value):
        raise RuntimeError('Invalid private NV checksum format')
    md5 = hashlib.md5(usedforsecurity=False)
    with open(os.open(data, os.O_RDONLY | os.O_NOFOLLOW), 'rb', closefd=True) as stream:
        while chunk := stream.read(1024 * 1024):
            md5.update(chunk)
    md5.update(SALT)
    if md5.hexdigest() != value:
        raise RuntimeError('Private NV salted checksum mismatch')
    return {'bytes': info.st_size, 'sha256': digest(data, info.st_size), 'salted_md5': value}


def assert_modem_stopped():
    names = {'cbd', 'rild', 'ril-lab.py', 'rfs-copy.py', 'run-ril-test.py', 'run-cbd-test.py'}
    for process in Path('/proc').glob('[0-9]*'):
        if process.name == str(os.getpid()):
            continue
        try:
            comm = (process / 'comm').read_text().strip()
            if comm in names:
                raise RuntimeError('Stop modem clients before changing private bindings')
            if comm.startswith('python'):
                args = (process / 'cmdline').read_bytes().split(b'\0')
                if any(Path(os.fsdecode(a)).name in names for a in args if a):
                    raise RuntimeError('Stop modem lab clients before changing private bindings')
        except (FileNotFoundError, ProcessLookupError):
            continue


def partition_fingerprints():
    """Identity partitions are read, never mounted, modified or exposed to vendor code."""
    devices = {}
    for name, (path, size) in PARTITION_SPECS.items():
        if path.is_symlink() or not stat.S_ISBLK(path.lstat().st_mode):
            raise RuntimeError('Unexpected original partition device')
        label = subprocess.check_output(['lsblk', '-n', '-o', 'PARTLABEL', str(path)], text=True).strip()
        if label != name:
            raise RuntimeError('Original partition mapping mismatch')
        actual_size = int(subprocess.check_output(['blockdev', '--getsize64', str(path)], text=True))
        if actual_size != size:
            raise RuntimeError('Original partition size mismatch')
        info = path.stat()
        devices[name] = f'{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}'
    mounted = {line.split()[2] for line in MOUNTINFO.read_text().splitlines()}
    if mounted.intersection(devices.values()):
        raise RuntimeError('An original identity/radio partition is mounted; stop for review')
    return {name: {'node': str(path), 'bytes': size, 'sha256': digest(path, size)}
            for name, (path, size) in PARTITION_SPECS.items()}


def model_fields(data):
    if (not isinstance(data, dict) or data.get('model') != 'SM-G965N' or
            not isinstance(data.get('bootloader'), str) or
            not re.fullmatch(r'G965N[A-Z0-9]+', data['bootloader'])):
        raise RuntimeError('Expected verified SM-G965N backup provenance')


def backup_provenance(efs, cpefs, manifest_path):
    if not manifest_path:
        raise RuntimeError('A verified recovery backup manifest is required')
    regular_info(manifest_path, maximum=1024 * 1024)
    manifest_bytes = read_regular(manifest_path, 1024 * 1024)
    manifest = json.loads(manifest_bytes)
    model_fields(manifest)
    if manifest.get('complete') is not True:
        raise RuntimeError('Recovery backup is incomplete')
    entries = manifest.get('partitions', [])
    if (not isinstance(entries, list) or not all(isinstance(e, dict) and isinstance(e.get('name'), str) for e in entries)
            or len({e['name'] for e in entries}) != len(entries)):
        raise RuntimeError('Duplicate or invalid recovery backup entries')
    entries = {e['name']: e for e in entries}
    if set(entries) != BACKUP_PARTITIONS or not all(
            type(e.get('bytes')) is int and e['bytes'] > 0 and
            isinstance(e.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', e['sha256'])
            for e in entries.values()):
        raise RuntimeError('Incomplete nine-partition backup manifest')
    current = partition_fingerprints()
    for name, expected in current.items():
        source = entries.get(name, {})
        if (source.get('bytes') != expected['bytes'] or
                source.get('sha256') != expected['sha256']):
            raise RuntimeError('Recovery backup belongs to a different/changed handset')
    for name, image in [('EFS', efs), ('CPEFS', cpefs)]:
        if not image:
            raise RuntimeError('Both private identity backup images are required')
        regular_info(image, size=current[name]['bytes'])
        if digest(image, current[name]['bytes']) != current[name]['sha256']:
            raise RuntimeError('Identity backup file checksum mismatch')
    return {'schema': 1, 'model': manifest['model'], 'bootloader': manifest['bootloader'],
            'source': current, 'backup_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'backup_sha256': {name: value['sha256'] for name, value in current.items()}}


def write_private_json(path, data):
    safe_components(path.parent)
    # Exclusive creation means a failed/partial stage can never overwrite old provenance.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with open(fd, 'w', closefd=True) as stream:
        json.dump(data, stream, sort_keys=True, indent=2); stream.write('\n')
        stream.flush(); os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_provenance():
    private_state()
    path = STATE / RECEIPT_NAME
    if not path.exists():
        raise RuntimeError('No private provenance receipt; legacy copies require explicit migration')
    info = regular_info(path, maximum=65536)
    if info.st_uid != ROOT_UID or stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError('Private provenance receipt must be root-owned and private')
    receipt = json.loads(read_regular(path, 65536))
    model_fields(receipt)
    if (receipt.get('schema') != 1 or not isinstance(receipt.get('source'), dict) or
            set(receipt['source']) != set(PARTITION_SPECS)):
        raise RuntimeError('Unsupported private provenance receipt')
    current = partition_fingerprints()
    if (not re.fullmatch(r'[0-9a-f]{64}', receipt.get('backup_manifest_sha256', '')) or
            receipt.get('backup_sha256') != {name: value['sha256'] for name, value in current.items()}):
        raise RuntimeError('Incomplete backup provenance receipt')
    if receipt['source'] != current:
        raise RuntimeError('Private receipt does not match this handset/original partitions')
    return receipt


def launch_receipt_bytes():
    private_state()
    path = STATE / RECEIPT_NAME
    info = regular_info(path, maximum=65536)
    if info.st_uid != ROOT_UID or stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError('Launch receipt must remain root-private')
    return read_regular(path, 65536)


def launch_receipt_digest():
    return hashlib.sha256(launch_receipt_bytes()).hexdigest()


def validate_launch_state(expected_receipt_sha256):
    """Child recheck under its lifetime lease, without original block access.

    The parent attests this exact receipt only after read_provenance verified
    original partitions. Migration never writes originals. A different receipt
    after the enqueue gap must require a fresh parent preflight.
    """
    assert_board()
    receipt_bytes = launch_receipt_bytes()
    if (not isinstance(expected_receipt_sha256, str) or
            not re.fullmatch(r'[0-9a-f]{64}', expected_receipt_sha256) or
            hashlib.sha256(receipt_bytes).hexdigest() != expected_receipt_sha256):
        raise RuntimeError('Private runtime changed since launcher preflight')
    receipt = json.loads(receipt_bytes)
    model_fields(receipt)
    validate_modem_state(receipt)
    verify_private_bindings()


def alias_preflight(path, target):
    parent = path.parent
    while not parent.exists() and not parent.is_symlink():
        parent = parent.parent
    safe_components(parent)
    if path.is_symlink():
        if os.readlink(path) != target:
            raise RuntimeError('Unexpected runtime alias')
    elif path.exists():
        raise RuntimeError('Runtime alias already occupied')


def modem_bindings_absent():
    if not os.path.ismount(ROOT):
        raise RuntimeError('Runtime not mounted')
    safe_components(ROOT)
    for target in [ROOT / 'mnt/vendor/efs', ROOT / 'mnt/vendor/cpefs',
                   ROOT / 'dev/block/platform/11120000.ufs/by-name/RADIO']:
        if os.path.ismount(target):
            raise RuntimeError('Private modem binding already exists; preserve it')
        # Existing paths must not redirect the fixed binding into another tree.
        current = target
        while not current.exists() and not current.is_symlink():
            current = current.parent
        safe_components(current)
        if target.exists() and (target.name == 'RADIO' or not target.is_dir() or any(target.iterdir())):
            raise RuntimeError('A fixed private binding path is already occupied')
    for name in ('efs', 'cpefs'):
        alias_preflight(ROOT / name, '/mnt/vendor/' + name)
    alias_preflight(ROOT / 'dev/block/by-name/RADIO', '../platform/11120000.ufs/by-name/RADIO')


def validate_modem_state(receipt):
    private_state()
    inventories = {name: tree_inventory(STATE / name, PARTITION_SPECS[name.upper()][1])
                   for name in ('efs', 'cpefs')}
    if not all(any(e['kind'] == 'file' for e in rows) for rows in inventories.values()):
        raise RuntimeError('Empty private NV tree')
    initial = receipt.get('initial_nv', {})
    if (not isinstance(initial, dict) or
            not re.fullmatch(r'[0-9a-f]{64}', initial.get('sha256', '')) or
            not re.fullmatch(r'[0-9a-f]{32}', initial.get('salted_md5', ''))):
        raise RuntimeError('Incomplete initial NV provenance')
    size = initial.get('bytes')
    if type(size) is not int or not 0 < size <= 16 * 1024 * 1024:
        raise RuntimeError('Invalid initial NV receipt')
    verify_nv(STATE / 'efs', expected_size=size)
    radio = STATE / 'RADIO'
    regular_info(radio, size=PARTITION_SPECS['RADIO'][1])
    if digest(radio, PARTITION_SPECS['RADIO'][1]) != receipt['source']['RADIO']['sha256']:
        raise RuntimeError('Private RADIO copy checksum mismatch')
    return inventories


def fixed_symlink(path, target):
    alias_preflight(path, target)
    if not path.is_symlink():
        path.symlink_to(target)


def attach_modem_copies():
    for name in ('efs', 'cpefs'):
        mount(STATE / name, ROOT / 'mnt/vendor' / name, '--bind')
        fixed_symlink(ROOT / name, '/mnt/vendor/' + name)
    target = ROOT / 'dev/block/platform/11120000.ufs/by-name/RADIO'
    safe_directory(target.parent)
    target.touch(exist_ok=False)
    run('mount', '--bind', STATE / 'RADIO', target)
    run('mount', '-o', 'remount,bind,ro', target)
    aliases = ROOT / 'dev/block/by-name'
    safe_directory(aliases)
    fixed_symlink(aliases / 'RADIO', '../platform/11120000.ufs/by-name/RADIO')
    device_nodes()
    cbd_permissions()



def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def safe_directory(path, mode=0o700):
    parent = path
    while not parent.exists() and not parent.is_symlink():
        parent = parent.parent
    safe_components(parent)
    path.mkdir(parents=True, exist_ok=True, mode=mode)
    safe_components(path)
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise RuntimeError('Expected a private directory')


def mount(source, target, *options):
    safe_directory(target)
    run('mount', *options, source, target)


def device_nodes(include_modem=True):
    if BASE == SENSOR_BASE and include_modem:
        raise RuntimeError('No modem devices in the dedicated sensor view')
    safe_components(ROOT / 'dev')
    if not os.path.ismount(ROOT):
        raise RuntimeError('Runtime not mounted')
    selected = ['null', 'zero', 'random', 'urandom']
    if BASE != MODEM_BASE:
        selected += ['ttyBCM', 'bbd_control', 'bbd_sensor', 'bbd_patch']
    if include_modem:
        selected += [p.name for p in Path('/dev').glob('umts_*')]
    for name in selected:
        source = Path('/dev') / name
        if source.exists():
            st = source.lstat()
            if not stat.S_ISCHR(st.st_mode):
                raise RuntimeError('Expected character device: ' + name)
            target = ROOT / 'dev' / name
            if target.exists() or target.is_symlink():
                old = target.lstat()
                if not stat.S_ISCHR(old.st_mode) or old.st_rdev != st.st_rdev:
                    raise RuntimeError('Unexpected existing runtime device: ' + name)
            else:
                os.mknod(target, stat.S_IFCHR | 0o600, st.st_rdev)
            if name.startswith('umts_'):
                os.chown(target, 1001, 1001)  # stock cbd drops to Android radio


def prepare(sensor_only=False, create_devices=True):
    if BASE == SENSOR_BASE and not sensor_only:
        raise RuntimeError('The dedicated sensor view only accepts sensor preparation')
    assert_board()
    safe_directory(BASE)
    safe_directory(STATE)
    private_state()
    safe_directory(DATA)
    if os.path.ismount(ROOT):
        raise RuntimeError('Runtime already mounted; reuse it or tear it down first')
    for partition, node in [('SYSTEM', '/dev/sda18'), ('VENDOR', '/dev/sda19')]:
        label = subprocess.check_output(['lsblk', '-n', '-o', 'PARTLABEL', node], text=True).strip()
        if label != partition:
            raise RuntimeError('Unexpected partition mapping')
        mount(node, BASE / partition, '-t', 'ext4', '-o', 'ro,noload')
    system = BASE / 'SYSTEM/system'
    vendor = BASE / 'VENDOR'
    if not (system / 'bin').is_dir():
        raise RuntimeError('Unexpected stock SYSTEM layout')
    safe_components(BASE)
    BASE.chmod(0o700)  # host users cannot traverse the private runtime
    mount('tmpfs', ROOT, '-t', 'tmpfs', '-o', 'mode=755,size=4m')
    for name in ('tmp', 'dev', 'proc', 'sys', 'data', 'apex/com.android.runtime'):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    mount(system, ROOT / 'system', '--bind')
    run('mount', '-o', 'remount,bind,ro', ROOT / 'system')
    mount(vendor, ROOT / 'vendor', '--bind')
    run('mount', '-o', 'remount,bind,ro', ROOT / 'vendor')
    apex = system / 'apex/com.android.runtime.release'
    if not apex.is_dir():
        raise RuntimeError('Stock Android runtime APEX missing')
    mount(apex, ROOT / 'apex/com.android.runtime', '--bind')
    run('mount', '-o', 'remount,bind,ro', ROOT / 'apex/com.android.runtime')
    mount('proc', ROOT / 'proc', '-t', 'proc')
    mount('/sys', ROOT / 'sys', '--bind')
    for name in ('vendor/gps', 'system/gps', 'log'):
        safe_directory(DATA / name)
    mount(DATA, ROOT / 'data', '--bind')
    # Individual character devices only: never bind the host's entire /dev.
    if create_devices:
        device_nodes(include_modem=not sensor_only)
    (ROOT / 'bin').symlink_to('system/bin')
    (ROOT / 'etc').symlink_to('system/etc')
    print('Owner vendor runtime prepared; no daemon started; no identity block devices exposed.')


def stage_modem(efs, cpefs, backup_manifest=None):
    assert_board()
    assert_modem_stopped()
    modem_bindings_absent()
    private_state()
    for name in ('efs', 'cpefs', 'RADIO', RECEIPT_NAME):
        if (STATE / name).exists() or (STATE / name).is_symlink():
            raise RuntimeError('Preserve existing private state; explicit archive/migration required')
    receipt = backup_provenance(efs, cpefs, backup_manifest)
    assert_modem_stopped()
    prepare_quarantined_extractions(efs, cpefs, receipt)
    radio = STATE / 'RADIO'
    with open(os.open(PARTITION_SPECS['RADIO'][0], os.O_RDONLY | os.O_NOFOLLOW), 'rb', closefd=True) as source, radio.open('xb') as output:
        shutil.copyfileobj(source, output, 1024 * 1024)
        output.flush(); os.fsync(output.fileno())
    receipt['initial_nv'] = verify_nv(STATE / 'efs')
    validate_modem_state(receipt)
    write_private_json(STATE / RECEIPT_NAME, receipt)
    attach_modem_copies()
    print('New private modem copies staged with verified provenance; no original identity partition mounted.')


def resume_modem():
    assert_board()
    assert_modem_stopped()
    modem_bindings_absent()
    receipt = read_provenance()
    validate_modem_state(receipt)
    assert_modem_stopped()
    attach_modem_copies()
    print('Existing private modem copies resumed after provenance and checksum verification; no data replaced.')


# Absolute offsets in the primary ext4 superblock only. No backup-superblock,
# inode, journal, checksum or other metadata changes are permitted here.
EFS_SUPERBLOCK_FIELDS = {
    'mount_time': (0x42c, '<I', 86400),
    'write_time': (0x430, '<I', 86400),
    'mount_count': (0x434, '<H', 4),
    'lifetime_write_kib': (0x578, '<Q', 4096),
}


def efs_superblock_proof(old, new, *, recovery_clock_rollback=False):
    if len(old) != len(new) or len(old) < 0x580:
        raise RuntimeError('Unexpected EFS snapshot size')
    if old[0x438:0x43a] != b'\x53\xef' or new[0x438:0x43a] != b'\x53\xef':
        raise RuntimeError('Missing primary ext4 superblock magic')
    masked_old = bytearray(old); masked_new = bytearray(new)
    fields = {}; changed = []
    for name, (offset, fmt, bound) in EFS_SUPERBLOCK_FIELDS.items():
        size = struct.calcsize(fmt)
        before = struct.unpack_from(fmt, old, offset)[0]
        after = struct.unpack_from(fmt, new, offset)[0]
        delta = after - before
        clock_field = name in ('mount_time', 'write_time')
        if not (recovery_clock_rollback and clock_field) and not 0 <= delta <= bound:
            raise RuntimeError('EFS superblock counter/time exceeds maintenance bounds')
        fields[name] = {'old': before, 'new': after, 'delta': delta}
        changed += [offset+i for i in range(size) if old[offset+i] != new[offset+i]]
        masked_old[offset:offset+size] = bytes(size)
        masked_new[offset:offset+size] = bytes(size)
    if recovery_clock_rollback:
        mount, write = fields['mount_time'], fields['write_time']
        if (mount['delta'] >= 0 or mount['delta'] != write['delta'] or
                mount['new'] == 0 or write['new'] == 0 or fields['mount_count']['delta'] == 0):
            raise RuntimeError('Expected a common backward EFS clock step with a new mount')
    if masked_old != masked_new:
        raise RuntimeError('EFS bytes changed outside the four approved superblock fields')
    if not changed:
        raise RuntimeError('No EFS superblock change; use ordinary provenance verification')
    return {'schema': 1, 'policy': ('primary-ext4-four-fields-clock-rollback-v1' if recovery_clock_rollback
                       else 'primary-ext4-four-fields-only-v1'),
            'changed_byte_offsets': changed, 'fields': fields,
            'all_other_bytes_sha256': hashlib.sha256(masked_old).hexdigest()}


def preservation_inventory():
    return {path.name: archive_tree_inventory(path)
            for pattern in ('archive-*', 'quarantine-*') for path in sorted(STATE.glob(pattern))}


def efs_checkpoint_chain(before, after, manifests, old_receipt, current):
    """Verify archived recovery checkpoints without relaxing a single hop.

    Only mount-count accumulation can exceed the original one-hop limit.
    Overall time/write bounds and byte identity outside four fields still apply.
    Checkpoint EFS snapshots must match complete same-handset manifests; callers
    also verify all nine source backup files before uploading selected evidence.
    """
    if not 1 <= len(manifests) <= 7 or len(set(manifests)) != len(manifests):
        raise RuntimeError('Expected one to seven distinct intermediate backup manifests')
    proofs = []; previous = before
    for path in manifests:
        raw = read_regular(path, 1024 * 1024)
        data = json.loads(raw); model_fields(data)
        rows = data.get('partitions', [])
        if (data.get('complete') is not True or data['bootloader'] != old_receipt['bootloader'] or
                not isinstance(rows, list) or len(rows) != len(BACKUP_PARTITIONS) or
                not all(isinstance(e, dict) and isinstance(e.get('name'), str) for e in rows)):
            raise RuntimeError('Invalid intermediate recovery manifest')
        entries = {e['name']: e for e in rows}
        if set(entries) != BACKUP_PARTITIONS or not all(
                type(e.get('bytes')) is int and e['bytes'] > 0 and
                isinstance(e.get('sha256'), str) and re.fullmatch(r'[0-9a-f]{64}', e['sha256'])
                for e in entries.values()):
            raise RuntimeError('Incomplete intermediate nine-partition manifest')
        for name in ('CPEFS', 'RADIO'):
            if any(entries[name][key] != current['source'][name][key] for key in ('bytes', 'sha256')):
                raise RuntimeError('Intermediate CPEFS/RADIO changed')
        if entries['EFS']['bytes'] != current['source']['EFS']['bytes']:
            raise RuntimeError('Intermediate EFS size changed')
        with verified_backup_snapshot(path.parent / 'EFS.img', entries['EFS']) as snapshot:
            next_bytes = read_regular(snapshot, entries['EFS']['bytes'])
        proof = efs_superblock_proof(previous, next_bytes)
        proofs.append({'manifest_sha256': hashlib.sha256(raw).hexdigest(),
                       'efs_sha256': entries['EFS']['sha256'], 'proof': proof})
        previous = next_bytes
    proofs.append({'efs_sha256': hashlib.sha256(after).hexdigest(),
                   'proof': efs_superblock_proof(previous, after)})
    # A chain must not multiply the existing day/write-budget limits.
    for name, (offset, fmt, bound) in EFS_SUPERBLOCK_FIELDS.items():
        delta = struct.unpack_from(fmt, after, offset)[0] - struct.unpack_from(fmt, before, offset)[0]
        maximum = bound * len(proofs) if name == 'mount_count' else bound
        if not 0 <= delta <= maximum:
            raise RuntimeError('Cumulative EFS checkpoint maintenance bounds exceeded')
    return {'schema': 1, 'policy': 'primary-ext4-four-fields-checkpoint-chain-v1', 'steps': proofs}


def efs_recovery_clock_proof(before, after, checkpoint_image, checkpoint_manifest, old_receipt, current):
    """Require a pinned intermediate snapshot and a subsequent ordinary forward step."""
    raw = read_regular(checkpoint_manifest, 1024 * 1024)
    data = json.loads(raw)
    model_fields(data)
    rows = data.get('partitions', [])
    if (data.get('complete') is not True or data['bootloader'] != old_receipt['bootloader']
            or not isinstance(rows, list) or len(rows) != len(BACKUP_PARTITIONS)
            or not all(isinstance(row, dict) and isinstance(row.get('name'), str) for row in rows)):
        raise RuntimeError('Invalid recovery-clock checkpoint manifest')
    entries = {row['name']: row for row in rows}
    if set(entries) != BACKUP_PARTITIONS or not all(
            type(row.get('bytes')) is int and row['bytes'] > 0
            and isinstance(row.get('sha256'), str)
            and re.fullmatch(r'[0-9a-f]{64}', row['sha256']) for row in entries.values()):
        raise RuntimeError('Incomplete recovery-clock checkpoint manifest')
    for name in ('CPEFS', 'RADIO'):
        if any(entries[name][field] != current['source'][name][field] for field in ('bytes', 'sha256')):
            raise RuntimeError('Recovery-clock checkpoint changed protected modem data')
    with verified_backup_snapshot(checkpoint_image, entries['EFS']) as snapshot:
        middle = read_regular(snapshot, entries['EFS']['bytes'])
    rollback = efs_superblock_proof(before, middle, recovery_clock_rollback=True)
    forward = efs_superblock_proof(middle, after)
    for name in ('mount_count', 'lifetime_write_kib'):
        total = rollback['fields'][name]['delta'] + forward['fields'][name]['delta']
        if total > EFS_SUPERBLOCK_FIELDS[name][2]:
            raise RuntimeError('Cumulative recovery-clock EFS bounds exceeded')
    return {'schema': 1, 'policy': 'primary-ext4-recovery-clock-checkpoint-v1',
            'checkpoint_manifest_sha256': hashlib.sha256(raw).hexdigest(),
            'steps': [rollback, forward]}


def revalidate_efs_superblock(old_efs, new_efs, cpefs, manifest, confirm=False, intermediate_manifests=None, *, recovery_clock_checkpoint=None):
    """Explicit provenance maintenance; never modify originals or working NV.

    Caller must hold the exclusive runtime lease. The old trusted image plus
    complete new same-handset backup establish the sole allowed byte changes.
    """
    if not confirm:
        raise RuntimeError('Explicit EFS superblock revalidation consent is required')
    if intermediate_manifests and recovery_clock_checkpoint:
        raise RuntimeError('Select one EFS checkpoint policy')
    assert_board(); assert_modem_stopped(); modem_bindings_absent(); private_state()
    receipt_path = STATE / RECEIPT_NAME
    old_bytes = launch_receipt_bytes()
    old_hash = hashlib.sha256(old_bytes).hexdigest()
    old = json.loads(old_bytes); model_fields(old)
    if old.get('schema') != 1 or not isinstance(old.get('source'), dict) or set(old['source']) != set(PARTITION_SPECS):
        raise RuntimeError('Unsupported old provenance receipt')
    for name, (node, size) in PARTITION_SPECS.items():
        source = old['source'][name]
        if (not isinstance(source, dict) or source.get('node') != str(node) or source.get('bytes') != size or
                not isinstance(source.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', source['sha256'])):
            raise RuntimeError('Malformed old provenance source')
    if (old.get('backup_sha256') != {name: source['sha256'] for name, source in old['source'].items()} or
            not isinstance(old.get('backup_manifest_sha256'), str) or
            not re.fullmatch(r'[0-9a-f]{64}', old['backup_manifest_sha256'])):
        raise RuntimeError('Incomplete old backup provenance')
    current = backup_provenance(new_efs, cpefs, manifest)
    if current['bootloader'] != old['bootloader']:
        raise RuntimeError('Bootloader provenance changed; stop for review')
    if any(current['source'][name] != old['source'][name] for name in ('CPEFS', 'RADIO')):
        raise RuntimeError('CPEFS/RADIO changed; superblock maintenance is forbidden')
    if old_efs is None:
        raise RuntimeError('Exact old verified EFS backup is required')
    with verified_backup_snapshot(old_efs, old['source']['EFS']) as before, verified_backup_snapshot(new_efs, current['source']['EFS']) as after:
        before_bytes = read_regular(before, old['source']['EFS']['bytes'])
        after_bytes = read_regular(after, current['source']['EFS']['bytes'])
        if recovery_clock_checkpoint:
            proof = efs_recovery_clock_proof(before_bytes, after_bytes, *recovery_clock_checkpoint, old, current)
        elif intermediate_manifests:
            proof = efs_checkpoint_chain(before_bytes, after_bytes, intermediate_manifests, old, current)
        else:
            proof = efs_superblock_proof(before_bytes, after_bytes)
    working = validate_modem_state(old)
    radio_before = file_inventory(STATE / 'RADIO')
    preserved = preservation_inventory()
    history = old.get('efs_superblock_revalidations', [])
    if not isinstance(history, list) or len(history) >= 32:
        raise RuntimeError('EFS provenance maintenance history requires manual review')
    suffix = str(time.time_ns())
    archived_receipt = STATE / ('provenance-before-efs-revalidation-' + suffix + '.json')
    updated = copy.deepcopy(old)
    updated.update(source=current['source'], backup_manifest_sha256=current['backup_manifest_sha256'],
                   backup_sha256=current['backup_sha256'])
    updated['efs_superblock_revalidations'] = history + [
        {'old_receipt_sha256': old_hash, 'old_receipt_copy': str(archived_receipt),
         'old_source': old['source'], 'new_source': current['source'],
         'new_backup_manifest_sha256': current['backup_manifest_sha256'], 'proof': proof}]
    if len((json.dumps(updated, sort_keys=True, indent=2)+'\n').encode()) > 65536:
        raise RuntimeError('Updated provenance receipt exceeds private bound')
    if (validate_modem_state(updated) != working or file_inventory(STATE / 'RADIO') != radio_before or
            preservation_inventory() != preserved or partition_fingerprints() != current['source']):
        raise RuntimeError('State changed during EFS revalidation; preserve everything for review')
    assert_modem_stopped(); modem_bindings_absent()
    if launch_receipt_bytes() != old_bytes:
        raise RuntimeError('Old receipt changed during EFS revalidation')
    # Preserve exact opaque bytes, including formatting, before atomic publish.
    fd = os.open(archived_receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with open(fd, 'wb', closefd=True) as stream:
        stream.write(old_bytes); stream.flush(); os.fsync(stream.fileno())
    if digest(archived_receipt) != old_hash:
        raise RuntimeError('Old receipt preservation verification failed')
    temporary = STATE / ('.provenance-revalidated-' + suffix + '.json')
    write_private_json(temporary, updated)
    os.replace(temporary, receipt_path)
    directory = os.open(STATE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    if (validate_modem_state(read_provenance()) != working or file_inventory(STATE / 'RADIO') != radio_before or
            preservation_inventory() != preserved):
        raise RuntimeError('Post-publish state verification failed; old receipt and all NV preserved')
    print('Explicit EFS superblock-only provenance revalidated; old receipt and all working/source data preserved; no daemon started.')


def archive_modem_state(efs, cpefs, backup_manifest, confirm=False):
    if not confirm:
        raise RuntimeError('Explicit private-state archive consent is required')
    assert_board()
    assert_modem_stopped()
    modem_bindings_absent()
    private_state()
    provenance = backup_provenance(efs, cpefs, backup_manifest)
    # Legacy copies are preserved, never adopted as trusted new provenance.
    snapshot = {name: archive_tree_inventory(STATE / name, PARTITION_SPECS[name.upper()][1])
                for name in ('efs', 'cpefs')}
    radio = STATE / 'RADIO'
    info = regular_info(radio)
    if info.st_size > PARTITION_SPECS['RADIO'][1]:
        raise RuntimeError('Legacy RADIO exceeds archive size bound')
    snapshot['RADIO'] = file_inventory(radio)
    receipt = STATE / RECEIPT_NAME
    if receipt.exists() or receipt.is_symlink():
        if regular_info(receipt).st_size > 65536:
            raise RuntimeError('Legacy receipt exceeds archive bound')
        snapshot[RECEIPT_NAME] = file_inventory(receipt)
    assert_modem_stopped()
    destination = STATE / ('archive-' + str(time.time_ns()))
    destination.mkdir(mode=0o700)
    write_private_json(destination / 'archive-inventory.json',
                       {'schema': 1, 'origin': 'preserved-not-adopted', 'snapshot': snapshot,
                        'verified_current_backup': provenance})
    for name in ('efs', 'cpefs', 'RADIO', RECEIPT_NAME):
        source = STATE / name
        if source.exists():
            source.rename(destination / name)
    if any(archive_tree_inventory(destination / name, PARTITION_SPECS[name.upper()][1]) != snapshot[name] for name in ('efs', 'cpefs')):
        raise RuntimeError('Archive verification failed; all moved data preserved for review')
    info = (destination / 'RADIO').lstat()
    archived_radio = {'bytes': info.st_size, 'sha256': digest(destination / 'RADIO', info.st_size),
                      'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid,
                      'gid': info.st_gid, 'mtime_ns': info.st_mtime_ns}
    if archived_radio != snapshot['RADIO']:
        raise RuntimeError('RADIO archive verification failed; preserved for review')
    if RECEIPT_NAME in snapshot and file_inventory(destination / RECEIPT_NAME) != snapshot[RECEIPT_NAME]:
        raise RuntimeError('Receipt archive verification failed; preserved for review')
    for directory in (destination, STATE):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    print('Private state archived with file hashes/metadata preserved; new explicit staging is required.')


def cbd_permissions():
    # Only private copies/nodes, never chmod/chown a stock partition or sysfs.
    private_state()
    safe_components(BASE)
    safe_components(DATA)
    BASE.chmod(0o700)
    for relative in ('', 'dev', 'dev/block', 'dev/block/platform',
                     'dev/block/platform/11120000.ufs',
                     'dev/block/platform/11120000.ufs/by-name', 'dev/block/by-name',
                     'mnt', 'mnt/vendor'):
        path = ROOT / relative
        if path.exists():
            safe_components(path)
            path.chmod(0o755)
    info = DATA.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != ROOT_UID or stat.S_IMODE(info.st_mode) & 0o022:
        raise RuntimeError('Runtime data must be a root-owned non-writable directory')
    DATA.chmod(0o755)
    log = DATA / 'log'
    safe_components(log, missing_leaf=True)
    log.mkdir(exist_ok=True)
    # Log is a directory; do not traverse vendor-controlled log content.
    fd = os.open(log, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchown(fd, 1001, 1001); os.fchmod(fd, 0o700)
    finally:
        os.close(fd)
    for name in ('efs', 'cpefs'):
        base = STATE / name
        tree_inventory(base)
        if not base.is_dir():
            raise RuntimeError('Missing working NV directory')
        private_permissions(base, 1001, 1001, 0o700, 0o600)
    radio = STATE / 'RADIO'
    regular_info(radio)
    private_permissions(radio, 1001, 1001, 0o700, 0o400)


def teardown():
    safe_components(BASE)
    for path in (ROOT, BASE / 'VENDOR', BASE / 'SYSTEM'):
        if path.exists() or path.is_symlink():
            safe_components(path)
    # Refuse busy mounts; never hide running processes with a lazy unmount.
    if os.path.ismount(ROOT):
        run('umount', '-R', ROOT)
    for name in ('VENDOR', 'SYSTEM'):
        target = BASE / name
        if os.path.ismount(target):
            run('umount', target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('up', 'up-sensors', 'down', 'refresh-devices', 'stage-modem', 'resume-modem', 'archive-modem-state', 'cbd-permissions', 'revalidate-efs-superblock'))
    parser.add_argument('--efs-backup', type=Path)
    parser.add_argument('--old-efs-backup', type=Path)
    parser.add_argument('--confirm-efs-superblock-revalidation', action='store_true')
    parser.add_argument('--intermediate-backup-manifest', type=Path, action='append', default=[],
                        help='Ordered verified recovery checkpoint manifests for bounded EFS-only metadata maintenance')
    parser.add_argument('--cpefs-backup', type=Path)
    parser.add_argument('--backup-manifest', type=Path)
    parser.add_argument('--confirm-archive-existing-private-state', action='store_true')
    args = parser.parse_args()
    # Normalize lexically, without following links; validation still checks every component.
    for name in ('efs_backup', 'old_efs_backup', 'cpefs_backup', 'backup_manifest'):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, Path(os.path.abspath(value)))
    args.intermediate_backup_manifest = [Path(os.path.abspath(p)) for p in args.intermediate_backup_manifest]
    if args.intermediate_backup_manifest and args.action != 'revalidate-efs-superblock':
        parser.error('Intermediate manifests are only for explicit superblock revalidation')
    if os.geteuid() != 0:
        raise SystemExit('Run as root on the handset')
    os.umask(0o077)
    assert_board()
    lock_fd = os.open(RUNTIME_LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    info = os.fstat(lock_fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != ROOT_UID or stat.S_IMODE(info.st_mode) & 0o077:
        os.close(lock_fd)
        raise SystemExit('Unexpected runtime lock file')
    with open(lock_fd, 'rb', closefd=True) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'down':
            teardown()
        elif args.action == 'refresh-devices':
            device_nodes()
        elif args.action == 'stage-modem':
            stage_modem(args.efs_backup, args.cpefs_backup, args.backup_manifest)
        elif args.action == 'resume-modem':
            resume_modem()
        elif args.action == 'archive-modem-state':
            archive_modem_state(args.efs_backup, args.cpefs_backup, args.backup_manifest,
                                args.confirm_archive_existing_private_state)
        elif args.action == 'revalidate-efs-superblock':
            revalidate_efs_superblock(args.old_efs_backup, args.efs_backup, args.cpefs_backup, args.backup_manifest,
                                      args.confirm_efs_superblock_revalidation, args.intermediate_backup_manifest)
        elif args.action == 'cbd-permissions':
            assert_modem_stopped()
            validate_modem_state(read_provenance())
            device_nodes()
            cbd_permissions()
        else:
            if os.path.ismount(ROOT):
                raise SystemExit('Runtime already mounted; existing runtime preserved')
            try:
                prepare(sensor_only=args.action == 'up-sensors')
            except BaseException:
                teardown()
                raise


if __name__ == '__main__':
    main()

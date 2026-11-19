#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Small RFS handler restricted to a private, checksummed NV working file.

Framing/checksum definitions: LineageOS libsamsung-ipc (see state-probe.py).
Modern request/response layouts were also cross-checked against the protocol
research in ztOS modem/README.md at8bfb09011757f06c68a055fbfd95ea07d5e4fbe1.
No third-party userspace implementation is copied. Arbitrary file opens are
denied: the CP cannot choose a host path. Never point this at original EFS.
"""
import errno
import hashlib
import os
from pathlib import Path
import stat
import struct

SALT = b'Samsung_Android_RIL'


class PrivateOpenCapture:
    """Bounded root-private OPEN/CLOSE evidence; never capture NV payloads.

    Caller verifies no symlink ancestors with the trusted runtime helper.
    Recording an OPEN is not permission to resolve it or access a host path.
    """
    def __init__(self, path):
        path = Path(path)
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('Expected an absolute private capture path')
        parent = path.parent.lstat()
        if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid() or parent.st_mode & 0o077):
            raise ValueError('Capture parent must be owned and private0700')
        self.fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.count = 0
        self.total = 0

    def record(self, message):
        if len(message) < 6 or struct.unpack_from('<I', message)[0] != len(message):
            raise ValueError('Invalid capture frame')
        if message[4] not in (0x11, 0x06):
            return  # No NV reads/writes or arbitrary payload dumps.
        if len(message) > 65536 or self.count >= 128 or self.total + len(message) + 4 > 1024 * 1024:
            raise ValueError('Private open-request capture bound exceeded')
        data = memoryview(struct.pack('<I', len(message)) + message)
        while data:
            count = os.write(self.fd, data)
            if count <= 0:
                raise OSError('Short private capture write')
            data = data[count:]
        os.fsync(self.fd)
        self.count += 1
        self.total += len(message) + 4

    def close(self):
        os.close(self.fd)


class WorkingNV:
    def __init__(self, directory):
        directory = Path(directory)
        if directory.is_symlink():
            raise ValueError('NV working directory must not be a symlink')
        self.path = directory / 'nv_data.bin'
        self.checksum = directory / 'nv_data.bin.md5'
        self.fd = os.open(self.path, os.O_RDWR | os.O_NOFOLLOW)
        try:
            info = os.fstat(self.fd)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 16 * 1024 * 1024:
                raise ValueError('Expected bounded regular NV working file')
            if self.checksum.is_symlink():
                raise ValueError('Checksum must not be a symlink')
            self.size = info.st_size
            if self.digest() != self.checksum.read_text().strip().lower():
                raise ValueError('Private NV checksum invalid; refuse modification')
        except BaseException:
            os.close(self.fd)
            raise

    def digest(self):
        data = os.pread(self.fd, self.size, 0)
        if len(data) != self.size:
            raise ValueError('Short NV read')
        return hashlib.md5(data + SALT).hexdigest()

    def close(self):
        os.close(self.fd)

    def handle(self, message):
        if len(message) < 6:
            raise ValueError('Truncated RFS header')
        size, command, ident = struct.unpack_from('<IBB', message)
        if size != len(message) or size > 16 * 1024 * 1024 + 14:
            raise ValueError('Invalid RFS frame length')
        if command in (1, 2):
            if size < 14:
                raise ValueError('Truncated NV request')
            offset, length = struct.unpack_from('<II', message, 6)
            valid = length <= self.size and offset <= self.size - length
            payload = b''
            written = 0
            if command == 1 and size != 14:
                valid = False
            if command == 2 and size != 14 + length:
                valid = False
            if valid and command == 2:
                # Only the already-open regular copy can be written. The CP's
                # offset cannot be interpreted as a path or a device address.
                written = os.pwrite(self.fd, message[14:], offset)
                if written != length:
                    raise OSError('Short private NV write')
                os.fsync(self.fd)
                temporary = self.checksum.with_suffix('.md5.g965n-new')
                with temporary.open('x') as stream:
                    stream.write(self.digest())
                    stream.flush(); os.fsync(stream.fileno())
                os.chown(temporary, self.path.stat().st_uid, self.path.stat().st_gid)
                temporary.replace(self.checksum)
            elif valid:
                payload = os.pread(self.fd, length, offset)
                valid = len(payload) == length
                written = len(payload) if valid else 0
            return struct.pack('<IBBBII', 15 + len(payload), command, ident,
                               int(valid), offset, written) + payload
        if command in (0x11, 0x06):
            # This diagnostic exposes no remote file namespace. Refuse opens,
            # and report no handle for closes; never parse or resolve its path.
            error = errno.ENOENT if command == 0x11 else errno.EBADF
            return struct.pack('<IBBii', 14, command, ident, -1, error)
        raise ValueError(f'Unsupported RFS command {command:#x}; no guessed response')

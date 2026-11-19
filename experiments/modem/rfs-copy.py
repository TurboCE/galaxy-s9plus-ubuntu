#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""RFS handler for private checksummed NV and opt-in bounded diagnostics.

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


class PrivateDiagnosticFiles:
    """Opt-in, bounded diagnostic namespace; never an EFS path resolver.

    Wire layouts checked against the owner's file-service interface. Only two
    observed diagnostic names are mapped to newly created private lab files.
    No audio defaults, calibration, identity or firmware files are synthesized.
    Contents can contain private network information and must not be published.
    """
    NAMES = {b'err/csdiag_mmrj_Info.dat': 'network-diagnostic.bin',
             b'err/csdiag_rf_Mipi.dat': 'rf-diagnostic.bin'}
    MAX_FILE = 256 * 1024
    MAX_IO = 64 * 1024

    def __init__(self, directory):
        directory = Path(directory)
        if not directory.is_absolute() or directory.resolve() != directory:
            raise ValueError('Diagnostic directory must be absolute without symlinks')
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('Diagnostic directory must be owned and private0700')
        self.directory = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        # Require an empty, dedicated directory. Existing files, including
        # hardlinks, must never become writable modem targets.
        if os.listdir(self.directory):
            os.close(self.directory)
            raise ValueError('Diagnostic directory must be new and empty')
        self.created = set()
        self.handles = {}
        self.next_handle = 1
        self.operations = 0

    def close(self):
        for fd in self.handles.values():
            os.close(fd)
        self.handles.clear()
        os.close(self.directory)

    def handle(self, message):
        if len(message) < 6:
            raise ValueError('Truncated diagnostic RFS header')
        size, command, ident = struct.unpack_from('<IBB', message)
        if size != len(message) or size > 14 + self.MAX_IO:
            raise ValueError('Invalid diagnostic RFS frame')
        self.operations += 1
        if self.operations > 4096:
            raise ValueError('Diagnostic operation bound exceeded')

        def reply(result, error=0, payload=b''):
            if command == 5:
                # The file-seek response includes a reserved zero word.
                return struct.pack('<IBBiii', 18, command, ident, 0, result, error)
            return struct.pack('<IBBii', 14 + len(payload), command, ident, result, error) + payload

        if command == 17:
            if size < 15:
                raise ValueError('Truncated diagnostic OPEN')
            flags, length = struct.unpack_from('<II', message, 6)
            name = message[14:]
            if length != len(name) or length > 128 or not name.endswith(b'\0') or b'\0' in name[:-1]:
                raise ValueError('Invalid diagnostic filename framing')
            target = self.NAMES.get(name[:-1])
            if target is None:
                return reply(-1, errno.ENOENT)
            # Android ARM64 flags are passed directly to open by the owner
            # service: 66=O_RDWR|O_CREAT, 0=O_RDONLY. No truncate/append escape.
            if flags not in (0, 66):
                return reply(-1, errno.EINVAL)
            if len(self.handles) >= 8:
                return reply(-1, errno.EMFILE)
            if target not in self.created:
                if flags == 0:
                    return reply(-1, errno.ENOENT)
                fd = os.open(target, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self.directory)
                self.created.add(target)
            else:
                fd = os.open(target, (os.O_RDONLY if flags == 0 else os.O_RDWR) | os.O_NOFOLLOW,
                             dir_fd=self.directory)
            info = os.fstat(fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                    info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_size > self.MAX_FILE):
                os.close(fd)
                raise ValueError('Invalid diagnostic backing file')
            handle = self.next_handle
            self.next_handle += 1
            self.handles[handle] = fd
            return reply(handle)
        if command not in (3, 4, 5, 6):
            raise ValueError('Unsupported diagnostic command')
        expected = 18 if command == 5 else 10 if command == 6 else 14
        if size < expected or (command != 4 and size != expected):
            raise ValueError('Invalid diagnostic request length')
        if command in (3, 4):
            count = struct.unpack_from('<I', message, 10)[0]
            if count > self.MAX_IO or (command == 4 and size != 14 + count):
                raise ValueError('Invalid diagnostic I/O length')
        handle = struct.unpack_from('<i', message, 6)[0]
        fd = self.handles.get(handle)
        if fd is None:
            return reply(0 if command == 3 else -1, errno.EBADF)
        try:
            if command == 6:
                os.close(fd)
                del self.handles[handle]
                return reply(0)
            if command == 3:
                data = os.read(fd, count)
                return reply(len(data), payload=data)
            position = os.lseek(fd, 0, os.SEEK_CUR)
            if command == 4:
                if position + count > self.MAX_FILE:
                    return reply(-1, errno.EFBIG)
                written = os.write(fd, message[14:])
                os.fsync(fd)
                return reply(written)
            offset, whence = struct.unpack_from('<II', message, 10)
            if whence not in (0, 1, 2):
                return reply(-1, errno.EINVAL)
            base = (0, position, os.fstat(fd).st_size)[whence]
            if base + offset > self.MAX_FILE:
                return reply(-1, errno.EFBIG)
            return reply(os.lseek(fd, base + offset, os.SEEK_SET))
        except OSError as error:
            return reply(0 if command == 3 else -1, error.errno)


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
    def __init__(self, directory, diagnostic_files=None):
        self.diagnostic_files = diagnostic_files
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
        if self.diagnostic_files is not None and command in (3, 4, 5, 6, 17):
            return self.diagnostic_files.handle(message)
        if command in (0x11, 0x06):
            # This diagnostic exposes no remote file namespace. Refuse opens,
            # and report no handle for closes; never parse or resolve its path.
            error = errno.ENOENT if command == 0x11 else errno.EBADF
            return struct.pack('<IBBii', 14, command, ident, -1, error)
        raise ValueError(f'Unsupported RFS command {command:#x}; no guessed response')

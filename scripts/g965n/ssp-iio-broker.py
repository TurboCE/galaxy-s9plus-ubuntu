#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""One verified SSP reader feeding real IIO devices; no synthetic samples."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import stat
import struct
import sys
import time

FRAME = struct.Struct('<IIQIIiiiIII')
DEVICE = '/dev/g965n-iio-bridge'


def magnetic_capture_policy(profile):
    """Optional bounded private diagnostic, never a compass/heading backend."""
    value = profile.get('magnetic_capture')
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {'output', 'seconds'} or
            type(value['seconds']) is not int or not 1 <= value['seconds'] <= 600 or
            not profile['accel']['enabled']):
        raise ValueError('Magnetic capture requires qualified acceleration and a bounded duration')
    path = Path(value['output'])
    if (path.parent != Path('/var/lib/g965n-sensors/magnetic-trials') or
            not path.name.endswith('.jsonl') or '..' in path.parts):
        raise ValueError('Magnetic capture must use the private trial directory')
    return value


def magnetic_initialization(profile):
    entry = profile.get('magnetic_initialization')
    if entry is None:
        return None
    if magnetic_capture_policy(profile) is None:
        raise ValueError('Magnetic initialization currently requires an explicit bounded capture')
    raw = read_owned(entry['path'], private=True)
    if (hashlib.sha256(raw).hexdigest() != entry.get('sha256') or
            len(raw) != entry.get('bytes')):
        raise ValueError('Private magnetic initialization checksum differs')
    value = json.loads(raw)
    if any(value.get(k) != v for k, v in {
            'schema': 1, 'model': 'SM-G965N', 'revision': 26, 'mag_type': 1,
            'stock_mag_position': 5, 'position_command_sent': False}.items()):
        raise ValueError('Wrong board magnetic initialization facts')
    for key, size in (('pdc', 27), ('mag_calibration', 13)):
        data = value.get(key)
        if (not isinstance(data, list) or len(data) != size or
                any(type(x) is not int or not 0 <= x <= 255 for x in data) or
                not any(data) or all(x == 255 for x in data)):
            raise ValueError('Missing or invalid actual magnetic initialization bytes')
    for key in ('own_stock_boot_sha256', 'own_efs_backup_sha256'):
        digest = value.get(key, '')
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Missing own-backup magnetic provenance')
    return value


def initialize_magnetic(probe, ssp, identity, value):
    # Samsung magnetic_common.c: initialize_magnetic_sensor. No F1 position
    # command: it would invalidate the separately qualified acceleration axes.
    fuse = ssp.read_magnetic_fuse(probe, identity['sensor_mask'])
    if not fuse['valid_factory_bytes']:
        raise RuntimeError('Magnetic factory fuse read is invalid; no calibration sent')
    probe.transaction(0xFD, bytes(value['pdc']))
    probe.transaction(0x46, bytes(value['mag_calibration']))


class MagneticCapture:
    """Record separate received batches, not invented simultaneous samples."""
    def __init__(self, policy):
        path = Path(policy['output'])
        for parent in (path.parent, *path.parent.parents):
            info = parent.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or
                    info.st_mode & (0o077 if parent == path.parent else 0o022)):
                raise ValueError('Unsafe private magnetic capture directory')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        self.stream = os.fdopen(fd, 'w')
        self.started = time.monotonic()
        self.deadline = self.started + policy['seconds']
        self.bytes = 0
        self.write({'schema': 1, 'kind': 'raw-magnetic-acceleration-capture',
                    'clock': 'host-monotonic-receive', 'heading_qualified': False})

    def write(self, value):
        line = json.dumps(value, separators=(',', ':')) + '\n'
        if self.bytes + len(line) > 2 * 1024 * 1024:
            raise RuntimeError('Magnetic capture exceeded private size bound')
        self.stream.write(line)
        self.stream.flush()
        self.bytes += len(line)

    def record(self, samples, now):
        if now >= self.deadline:
            return False
        actual = {str(k): samples[k] for k in (0, 4) if samples.get(k)}
        if actual:
            self.write({'receive_monotonic_s': now, 'samples': actual})
        return True

    def close(self):
        self.stream.close()


def read_owned(path, private=False):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise ValueError('Expected absolute ordinary root-owned file')
    parent = path.parent.resolve(strict=True)
    for part in (parent, *parent.parents):
        info = part.stat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('File parent is writable outside root')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or
                info.st_mode & (0o077 if private else 0o022)):
            raise ValueError('Unsafe file owner, mode or links')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            return stream.read()
    finally:
        os.close(fd)


def pinned(entry):
    if not isinstance(entry, dict) or not {'path', 'sha256'} <= set(entry):
        raise ValueError('Missing pinned file metadata')
    data = read_owned(entry['path'])
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise ValueError('Pinned file checksum changed')
    if 'bytes' in entry and len(data) != entry['bytes']:
        raise ValueError('Pinned file size changed')
    return data


def load_module(entry, name):
    data = pinned(entry)
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = entry['path']
    exec(compile(data, entry['path'], 'exec'), module.__dict__)
    return module


def optional_sensor_enabled(profile, name):
    policy = profile.get(name, {'enabled': False})
    if not isinstance(policy, dict) or set(policy) != {'enabled'} or type(policy['enabled']) is not bool:
        raise ValueError(f'{name} enable must be an explicit boolean')
    return policy['enabled']


def verify_profile(path):
    data = read_owned(path, private=True)
    expected = os.environ.get('G965N_SENSOR_PROFILE_SHA256', '')
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Supervisor profile checksum differs')
    profile = json.loads(data)
    if profile.get('schema') != 1 or profile.get('model') != 'SM-G965N':
        raise ValueError('Wrong sensor profile schema/model')
    own = profile['programs']['broker']
    if Path(own['path']).resolve() != Path(__file__).resolve():
        raise ValueError('Broker path differs from pinned program')
    pinned(own)
    receipt = json.loads(pinned(profile['kernel_receipt']))
    if receipt['boot_sha256'] != profile['expected_boot_sha256'] or not receipt.get('built_in_iio'):
        raise ValueError('Profile requires the exact IIO-enabled BOOT')
    load_module(profile['programs']['kernel_verifier'], 'sensor_kernel_verifier').verify_kernel(receipt)
    for name in ('module', 'iio_bridge', 'hub_patch'):
        pinned(profile[name])
    if profile['iio_bridge'].get('device') != DEVICE:
        raise ValueError('Wrong IIO feed device')
    if not isinstance(profile.get('accel'), dict) or type(profile['accel'].get('enabled')) is not bool:
        raise ValueError('Explicit acceleration policy required')
    if profile['accel']['enabled']:
        evidence = json.loads(pinned(profile['orientation_evidence']))
        matrix = profile['accel'].get('mount_matrix')
        if (profile['accel'].get('range_g') != 8 or not evidence.get('geometry_validated') or
                evidence.get('status') != 'verified' or evidence.get('model') != 'SM-G965N' or evidence.get('range_g') != 8 or
                evidence.get('mount_matrix') != matrix):
            raise ValueError('Acceleration mounting evidence does not match')
    magnetic_capture_policy(profile)
    magnetic_initialization(profile)
    for name in ('pressure', 'proximity'):
        optional_sensor_enabled(profile, name)
    return profile


class Feed:
    def __init__(self, fd):
        self.fd = fd
        self.seq = 0

    def publish(self, kind, values=(0, 0, 0)):
        values = tuple(values)
        if len(values) != 3 or any(type(v) is not int for v in values):
            raise ValueError('Feed fields must be three actual integers')
        if kind == 1:
            if len(values) != 3 or any(type(v) is not int or not -32768 <= v <= 32767 for v in values):
                raise ValueError('Invalid actual acceleration tuple')
        elif kind == 2:
            if len(values) != 3 or type(values[0]) is not int or not 0 <= values[0] <= 0x7fffffff or values[1:] != (0, 0):
                raise ValueError('Invalid actual illuminance tuple')
        elif kind == 4:
            if not 0 < values[0] <= 0x7fffff or values[1:] != (0, 0):
                raise ValueError('Invalid actual LPS22H pressure tuple')
        elif kind == 5:
            if values[0] not in (0, 1) or values[1:] != (0, 0):
                raise ValueError('Invalid actual TMD4906 detection tuple')
        elif kind != 3 or values != (0, 0, 0):
            raise ValueError('Invalid heartbeat')
        if self.seq == 0xffffffffffffffff:
            raise OverflowError('Feed sequence exhausted')
        frame = FRAME.pack(1, FRAME.size, self.seq + 1, kind, 1 if kind == 1 else 0, *values, 0, 0, 0)
        if os.write(self.fd, frame) != len(frame):
            raise RuntimeError('Incomplete IIO feed write')
        self.seq += 1


def publish_actual(probe, selected, feed, seen, last_accel, now):
    for sensor in selected:
        values = probe.samples.get(sensor, [])
        if not values:
            continue
        latest = values[-1]
        if sensor == 0:
            feed.publish(1, latest)
            last_accel = now
        elif sensor == 9:
            feed.publish(2, (latest[0], 0, 0))
        elif sensor == 5:
            feed.publish(4, (latest[0], 0, 0))
        elif sensor == 7:
            feed.publish(5, (latest[0], 0, 0))
        elif sensor == 4:
            pass  # Private raw diagnostic only; never publish an unqualified heading.
        else:
            raise ValueError('Unreviewed sensor in broker')
        probe.samples[sensor] = []
        seen.add(sensor)
    # The firmware may emit other known record types; do not retain them forever.
    for sensor in probe.samples:
        if sensor not in selected:
            probe.samples[sensor] = []
    return last_accel


def pipe_descriptor(fd, writable):
    if fd < 3 or not stat.S_ISFIFO(os.fstat(fd).st_mode):
        raise ValueError('Supervisor channel must be a passed pipe')
    mode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
    if mode != (os.O_WRONLY if writable else os.O_RDONLY):
        raise ValueError('Wrong supervisor pipe direction')


class StopChannel:
    def __init__(self, fd):
        self.fd = fd
        self.message = bytearray()

    def requested(self):
        if not select.select([self.fd], [], [], 0)[0]:
            return False
        chunk = os.read(self.fd, 32)
        if not chunk:
            return True
        self.message.extend(chunk)
        if not b'STOP\n'.startswith(self.message):
            raise ValueError('Invalid supervisor stop message')
        return self.message == b'STOP\n'


def wait_transport(ssp, channel, stopping, seconds):
    deadline = time.monotonic() + seconds
    while not stopping():
        if channel.requested():
            return False
        try:
            ssp.require_transport_ready()
            return True
        except RuntimeError as error:
            if str(error) != 'Hub transport not ready; no sensor enabled':
                raise
        if time.monotonic() >= deadline:
            raise RuntimeError('Hub transport readiness deadline expired')
        select.select([channel.fd], [], [], .1)
    return False


def run(profile, ssp, ready_fd, stop_fd):
    enabled = []
    stopping = False
    def stop(_signum, _frame):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with ssp.acquire_probe_lock():
        channel = StopChannel(stop_fd)
        if not wait_transport(ssp, channel, lambda: stopping, min(30, profile.get('timeouts', {}).get('startup', 60))):
            return
        probe = ssp.Probe('lux18')
        feed_fd = None
        capture = None
        try:
            identity = ssp.acquire_hub_identity(probe)
            expected = profile['identity']
            if any(identity.get(k) != expected.get(k) for k in ('chip_id', 'firmware', 'sensor_mask')):
                raise ValueError('Live hub identity differs from qualified profile')
            selected = [0, 9] if profile['accel']['enabled'] else [9]
            for name, sensor in (('pressure', 5), ('proximity', 7)):
                if optional_sensor_enabled(profile, name):
                    selected.append(sensor)
            capture_policy = magnetic_capture_policy(profile)
            if capture_policy is not None:
                selected.append(4)  # Calibrated only; never enable conflicting raw2/3.
            ssp.require_advertised(selected, identity['sensor_mask'])
            if 0 in selected and probe.transaction(0xE1, length=1) != b'\x08':
                raise ValueError('Live acceleration range is not 8G; no sensor enabled')
            magnetic_init = magnetic_initialization(profile)
            if magnetic_init is not None:
                initialize_magnetic(probe, ssp, identity, magnetic_init)
            feed_fd = os.open(DEVICE, os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            info = os.fstat(feed_fd)
            if not stat.S_ISCHR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
                raise ValueError('Unsafe IIO feed character device')
            feed = Feed(feed_fd)
            if capture_policy is not None:
                capture = MagneticCapture(capture_policy)
            for sensor in selected:
                probe.samples[sensor] = []
                enabled.append(sensor)  # Attempt cleanup even if A1 acknowledgement is lost.
                probe.transaction(0xA1, struct.pack('<BiiB', sensor, ssp.SAMPLE_DELAY_MS, 0, 0))
            started = time.monotonic()
            seen = set()
            ready = False
            last_accel = None
            next_heartbeat = started
            while not stopping:
                if channel.requested():
                    break
                ssp.require_transport_ready()
                probe.pump(.05)
                now = time.monotonic()
                if capture is not None and not capture.record(probe.samples, now):
                    ssp.disable_sensors(probe, [4])
                    enabled.remove(4)
                    selected.remove(4)
                    seen.discard(4)
                    probe.samples[4] = []
                    capture.close()
                    capture = None
                    print(json.dumps({'magnetic_capture_completed': True,
                                      'magnetic_sensor_removed': True}), flush=True)
                last_accel = publish_actual(probe, selected, feed, seen, last_accel, now)
                if now >= next_heartbeat:
                    feed.publish(3)
                    next_heartbeat = now + .25
                if not ready and seen == set(selected):
                    if os.write(ready_fd, b'READY\n') != 6:
                        raise RuntimeError('Incomplete supervisor readiness message')
                    ready = True
                if not ready and now - started > profile.get('timeouts', {}).get('startup', 60):
                    raise RuntimeError('No actual first sensor reading within startup bound')
                if 0 in selected and last_accel is not None and now - last_accel > 1.5:
                    raise RuntimeError('Continuous acceleration stream became stale')
            print(json.dumps({'broker_stopped': True, 'published': feed.seq,
                              'unparsed_frames': probe.unparsed}), flush=True)
        finally:
            try:
                ssp.disable_sensors(probe, enabled)
            finally:
                if feed_fd is not None:
                    os.close(feed_fd)  # Invalidates/removes real IIO devices even on cleanup failure.
                os.close(probe.fd)
                if capture is not None:
                    capture.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--sensor-service-child', action='store_true')
    parser.add_argument('--ready-fd', type=int, required=True)
    parser.add_argument('--stop-fd', type=int, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not args.sensor_service_child:
        parser.error('Explicit root sensor-service child mode required')
    if args.ready_fd == args.stop_fd:
        parser.error('Supervisor channels must be separate')
    pipe_descriptor(args.ready_fd, True)
    pipe_descriptor(args.stop_fd, False)
    profile = verify_profile(args.profile)
    ssp = load_module(profile['programs']['ssp_probe'], 'g965n_verified_ssp')
    run(profile, ssp, args.ready_fd, args.stop_fd)


if __name__ == '__main__':
    main()

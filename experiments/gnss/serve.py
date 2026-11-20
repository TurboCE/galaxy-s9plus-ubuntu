#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Serve one GeoClue client using the checked SM-G965N GNSS runtime."""
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path('/run/g965n-sensor-runtime/root')
GPS_DATA = ROOT / 'data/vendor/gps'
STATE = Path('/var/lib/g965n-sensors')
TRIAL_NAMES = ('.gpsd.lock', 'chip.info', '.flp.interface.pipe.to_gpsd',
               '.pipe.gpsd_to_lhd.to_client', 'LogConsole.from')
LIBRARIES = '/vendor/lib64:/system/lib64:/apex/com.android.runtime/lib64:/apex/com.android.runtime/lib64/bionic'


def checked(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError(f'GNSS input differs from its pin: {path.name}')
    return data


def load(path):
    spec = importlib.util.spec_from_file_location('g965n_sensor_supervisor', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stop(process, timeout=8):
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def utc_synchronized():
    # The marker is per boot. timedated also checks the current kernel state.
    if not Path('/run/systemd/timesync/synchronized').is_file():
        return False
    try:
        result = subprocess.run(
            ['busctl', 'get-property', 'org.freedesktop.timedate1',
             '/org/freedesktop/timedate1', 'org.freedesktop.timedate1',
             'NTPSynchronized'], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == 'b true'


def worker(root, supervisor, inject_utc):
    restrict = load(supervisor).drop_vendor_privileges
    for name in ('system', 'vendor', 'apex/com.android.runtime'):
        source, dest = ROOT / name, root / name
        if not os.path.ismount(source) or not os.statvfs(source).f_flag & os.ST_RDONLY:
            raise RuntimeError('Expected read-only mounted sensor vendor runtime')
        dest.mkdir(parents=True)
        subprocess.run(['mount', '--bind', source, dest], check=True)
        subprocess.run(['mount', '-o', 'remount,bind,ro', dest], check=True)
    for name in ('proc', 'sys', 'dev/socket', 'cache', 'data/vendor/gps',
                 'data/system/gps', 'tmp'):
        (root / name).mkdir(parents=True)
    subprocess.run(['mount', '-t', 'proc', '-o', 'ro,nosuid,nodev,noexec', 'proc', root / 'proc'], check=True)
    for name in ('null', 'zero', 'random', 'urandom'):
        node = root / 'dev' / name
        node.touch()
        subprocess.run(['mount', '--bind', '/dev/' + name, node], check=True)
    subprocess.run(['mount', '--bind', GPS_DATA, root / 'data/vendor/gps'], check=True)

    def enter():
        os.chroot(root)
        os.chdir('/')
        restrict()

    environment = {'LD_LIBRARY_PATH': LIBRARIES}
    daemon = subprocess.Popen(['/vendor/bin/hw/gpsd', '-c', '/vendor/etc/gnss/gps.xml'],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, env=environment, preexec_fn=enter)
    try:
        time.sleep(2)
        if daemon.poll() is not None:
            raise RuntimeError('Vendor GNSS exited before HAL start')
        # Only the HAL gets FD 3. Vendor logs and HAL status text cannot reach GeoClue.
        os.dup2(sys.stdout.fileno(), 3)
        command = ['/trial/hal', '24', '--serve-nmea-fd3']
        if inject_utc:
            command.append('--inject-current-utc')
        client = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  pass_fds=(3,), env=environment, preexec_fn=enter)
        with client.stdout:
            for line in iter(lambda: client.stdout.readline(128), b''):
                prefix = b'GNSS UTC injection result: '
                if inject_utc and line.startswith(prefix):
                    try:
                        result = int(line[len(prefix):].strip())
                    except ValueError:
                        continue
                    print(f'GNSS HAL UTC assistance result: {result}', file=sys.stderr, flush=True)
        sys.exit(client.wait())
    finally:
        daemon.terminate()
        stop(daemon, 2)


def serve():
    with socket.socket(fileno=os.dup(0)) as peer:
        _, uid, _ = struct.unpack('3i', peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if uid != pwd.getpwnam('geoclue').pw_uid:
            raise RuntimeError('GNSS endpoint accepts only GeoClue')
        # Empty accept() connections are valid requests. Client input is never passed to the HAL.
        peer.settimeout(2)
        base = Path(__file__).resolve().parent
        cfg_path = STATE / 'profile.json'
        cfg = json.loads(checked(cfg_path, (STATE / 'profile.sha256').read_text().strip()))
        supervisor = Path(cfg['programs']['supervisor']['path'])
        checked(supervisor, cfg['programs']['supervisor']['sha256'])
        load(supervisor).validate_profile(cfg)
        pins = json.loads((base / 'pins.json').read_text())
        checked(ROOT / 'vendor/bin/hw/gpsd', pins['vendor_daemon'])
        checked(ROOT / 'vendor/etc/gnss/gps.xml', pins['vendor_config'])
        hal = checked(base / 'hal', pins['hal'])
        with contextlib.ExitStack() as stack:
            for path, operation in (('/run/g965n-gnss.lock', fcntl.LOCK_EX),
                                    ('/run/g965n-sensor-runtime.lock', fcntl.LOCK_SH)):
                fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                stack.callback(os.close, fd)
                fcntl.flock(fd, operation | fcntl.LOCK_NB)
            if not stat.S_ISFIFO((GPS_DATA / '.pipe.gpsd_to_lhd.to_server').stat().st_mode):
                raise RuntimeError('Sensor hub GPS IPC is not ready')
            if any(os.path.lexists(GPS_DATA / name) for name in TRIAL_NAMES):
                raise RuntimeError('Found existing GPS state; preserving it')
            directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='g965n-gnss-', dir='/run')))
            root = directory / 'root'
            (root / 'trial').mkdir(parents=True)
            image = root / 'trial/hal'
            image.write_bytes(hal)
            image.chmod(0o500)
            command = ['unshare', '--mount', '--propagation', 'private',
                '--net', '--pid', '--fork', '--kill-child', sys.executable, __file__,
                '--worker', str(root), str(supervisor)]
            if utc_synchronized():
                command.append('--inject-current-utc')
            session = subprocess.Popen(command, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE)
            frames = 0
            try:
                while True:
                    ready, _, _ = select.select([peer, session.stdout], [], [])
                    if peer in ready:
                        break
                    chunk = os.read(session.stdout.fileno(), 4096)
                    if not chunk:
                        if session.wait() != 0:
                            raise RuntimeError('GNSS worker exited unsuccessfully')
                        break
                    peer.sendall(chunk)
                    frames += chunk.count(b'\n')
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            finally:
                session.stdin.close()
                stop(session)
                session.stdout.close()
                for name in TRIAL_NAMES:
                    artifact = GPS_DATA / name
                    with contextlib.suppress(FileNotFoundError):
                        mode = artifact.lstat().st_mode
                        if stat.S_ISFIFO(mode) or stat.S_ISREG(mode):
                            artifact.unlink()
                print(f'GNSS session closed after {frames} NMEA sentences', flush=True)


def terminate(signum, frame):
    raise SystemExit(0)


if __name__ == '__main__':
    os.umask(0o077)
    signal.signal(signal.SIGTERM, terminate)
    if len(sys.argv) >= 2 and sys.argv[1] == '--worker':
        if len(sys.argv) not in (4, 5) or sys.argv[4:] not in ([], ['--inject-current-utc']):
            raise SystemExit('Invalid GNSS worker arguments')
        worker(Path(sys.argv[2]), Path(sys.argv[3]), len(sys.argv) == 5)
    else:
        serve()

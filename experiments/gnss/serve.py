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
import re
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

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


def diagnostic_message(packet):
    """Select errors only; discard location records and redact identifiers."""
    parts = [p for p in packet.split(b'\0') if p]
    if not parts:
        return None
    text = parts[-1].decode('ascii', errors='replace')
    if not re.search(r'error|fail|timeout|lhd|receiver', text, re.I):
        return None
    if re.search(r'\b(?:lat|lon|latitude|longitude|location|position|nmea|imei|imsi|iccid|serial|token|password)\b', text, re.I):
        return None
    text = re.sub(r'https?://\S+', '[URL]', text)
    text = re.sub(r'0x[0-9a-f]+|[-+]?\d[\d.eE+-]*', '#', text, flags=re.I)
    return re.sub(r'[^a-zA-Z# /_.,:()\[\]=-]', ' ', text)[:240]


def log_summary(path):
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as listener:
        listener.bind(path)
        os.chmod(path, 0o600)
        forwarded = 0
        while True:
            message = diagnostic_message(listener.recv(8192))
            if message and forwarded < 60:
                print('GNSS vendor diagnostic: ' + message, file=sys.stderr, flush=True)
                forwarded += 1


def watch_hal(daemon, client, inject_utc):
    """Monitor both processes even when the HAL keeps its stdout pipe open."""
    pending = b''
    while True:
        status = daemon.poll()
        if status is not None:
            raise RuntimeError(f'Vendor GNSS exited after HAL start: {status}')
        if not select.select([client.stdout], [], [], 0.5)[0]:
            continue
        chunk = os.read(client.stdout.fileno(), 4096)
        if not chunk:
            return client.wait()
        pending += chunk
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            prefix = b'GNSS UTC injection result: '
            if inject_utc and line.startswith(prefix):
                try:
                    result = int(line[len(prefix):].strip())
                except ValueError:
                    continue
                print(f'GNSS HAL UTC assistance result: {result}', file=sys.stderr, flush=True)
            elif re.fullmatch(
                rb'(?:GNSS extension (?:gps-xtra|agps|agps_ril|gps-debug|gnss_configuration) available: [01]|'
                rb'GNSS callbacks: status=\d+ satellites=\d+ nmea=\d+ location=\d+|'
                rb'GNSS checksum-valid NMEA: \d+, forwarded: \d+|'
                rb'GNSS capability mask: \d+|GNSS status code \d+ occurred \d+ times|'
                rb'GNSS XTRA init result: -?\d+|'
                rb'GNSS XTRA injection result: -?\d+ \(bytes=\d+\)|'
                rb'GNSS live: satellite_callbacks=\d+ visible_max=\d+ fixes=\d+ nmea=\d+)', line):
                print(line.decode('ascii'), file=sys.stderr, flush=True)
        if len(pending) > 8192:
            pending = b''


def receiver_config(raw):
    """Disable this daemon's optional Android sensor-service dependency."""
    document = ET.fromstring(raw)
    elements = document.findall('{http://www.glpals.com/}hal')
    if document.tag != '{http://www.glpals.com/}glgps' or len(elements) != 1:
        raise RuntimeError('Unexpected vendor GNSS configuration structure')
    text = raw.decode('utf-8')
    matches = list(re.finditer(r'<hal\b[^>]*>', text))
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one GNSS HAL configuration tag')
    match = matches[0]
    tag = match.group()
    if 'SensorsEnable' in elements[0].attrib:
        tag, count = re.subn(r'\bSensorsEnable\s*=\s*["\'][^"\']*["\']',
                             'SensorsEnable="false"', tag)
        if count != 1:
            raise RuntimeError('Ambiguous GNSS sensor option')
    else:
        tag = tag.replace('<hal', '<hal SensorsEnable="false"', 1)
    result = (text[:match.start()] + tag + text[match.end():]).encode('utf-8')
    changed = ET.fromstring(result)
    expected = dict(elements[0].attrib, SensorsEnable='false')
    if changed.find('{http://www.glpals.com/}hal').attrib != expected:
        raise RuntimeError('GNSS configuration changed beyond the sensor option')
    return result


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

    logger = None
    if os.environ.get('G965N_GNSS_DIAGNOSTICS') == '1':
        endpoint = root / 'dev/socket/logdw'
        logger = subprocess.Popen([sys.executable, __file__, '--log-summary', str(endpoint)],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        for _ in range(50):
            if endpoint.exists():
                break
            time.sleep(0.02)
    config = root / 'trial/gps.xml'
    config.write_bytes(receiver_config((root / 'vendor/etc/gnss/gps.xml').read_bytes()))
    config.chmod(0o400)
    environment = {'LD_LIBRARY_PATH': LIBRARIES}
    daemon = subprocess.Popen(['/vendor/bin/hw/gpsd', '-c', '/trial/gps.xml'],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, env=environment, preexec_fn=enter)
    client = None
    try:
        time.sleep(2)
        if daemon.poll() is not None:
            raise RuntimeError('Vendor GNSS exited before HAL start')
        # Only the HAL gets FD 3. Vendor logs and HAL status text cannot reach GeoClue.
        os.dup2(sys.stdout.fileno(), 3)
        command = ['/trial/hal', '24', '--serve-nmea-fd3']
        if inject_utc:
            command.append('--inject-current-utc')
        descriptors = (3,)
        aid = root / 'trial/xtra.dat'
        if aid.is_file():
            fd = os.open(aid, os.O_RDONLY | os.O_NOFOLLOW)
            if fd != 4:
                os.dup2(fd, 4)
                os.close(fd)
            descriptors = (3, 4)
            command.append('--xtra-fd4')
        client = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  pass_fds=descriptors, env=environment, preexec_fn=enter)
        if len(descriptors) == 2:
            os.close(4)
        with client.stdout:
            sys.exit(watch_hal(daemon, client, inject_utc))
    finally:
        if client and client.poll() is None:
            client.terminate()
            stop(client, 2)
        daemon.terminate()
        stop(daemon, 2)
        if logger:
            logger.terminate()
            stop(logger, 2)


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
            assistance = base / 'assistance.py'
            if assistance.is_file():
                cached = load(assistance).read_cache()
                if cached:
                    aid = root / 'trial/xtra.dat'
                    aid.write_bytes(cached)
                    aid.chmod(0o400)
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
    if len(sys.argv) == 3 and sys.argv[1] == '--log-summary':
        log_summary(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == '--worker':
        if len(sys.argv) not in (4, 5) or sys.argv[4:] not in ([], ['--inject-current-utc']):
            raise SystemExit('Invalid GNSS worker arguments')
        worker(Path(sys.argv[2]), Path(sys.argv[3]), len(sys.argv) == 5)
    else:
        serve()

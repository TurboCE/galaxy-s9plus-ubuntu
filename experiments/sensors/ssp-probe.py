#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read identity and bounded motion/light samples from a ready sensor hub.

Protocol fields/commands follow LineageOS's GPL Exynos9810 ssp.h/ssp_data.c
(commit 6a9461f9460ca51d1217e5069a5d5556fcc79e63). This is an original diagnostic
client, not a copy of a third-party userspace daemon. One transaction at a time.
Default mode sends no sleep/wake commands. Explicit --ap-awake sends only two
volatile AP-awake notifications; no sleep, calibration or persistent writes.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import struct
import stat
import time


PROBE_LOCK_PATH = '/run/lock/g965n-ssp-probe.lock'


@contextmanager
def acquire_probe_lock():
    """Hold the canonical, strictly root-owned SSP lease without adopting it.

    Existing metadata is never repaired here. The operator must migrate an old
    file only after confirming every previous owner has stopped. Never unlink
    the lock: waiters and brokers must continue referring to the same inode.
    """
    fd = os.open(PROBE_LOCK_PATH, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        def verify():
            held = os.fstat(fd)
            named = os.stat(PROBE_LOCK_PATH, follow_symlinks=False)
            if (not stat.S_ISREG(held.st_mode) or held.st_uid != 0 or
                    held.st_nlink != 1 or stat.S_IMODE(held.st_mode) != 0o600 or
                    (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino)):
                raise RuntimeError('Unsafe SSP lock metadata or replaced lock path')
        verify()
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Do not use an inode replaced while we were acquiring the lease.
        verify()
        yield fd
    finally:
        os.close(fd)


# Layout facts from the pinned Lineage sensor_value/get_light_sensordata.
# G965N reference config uses REPORT_LUX with one-byte gain (lux18).
# Exact pinned star2lte configuration: magnetic overflow enabled, TMD4906.
SENSOR_FORMATS = {0: '<hhh', 1: '<iii', 2: '<hhhhhhB', 3: '<hhh',
                  4: '<hhhBB', 5: '<ih', 7: '<BH', 10: '<H',
                  16: '<iiiiB', 17: '<iiiiB', 34: '<Bh'}
SENSOR_GROUPS = {'motion': [0, 1], 'light': [9], 'all': [0, 1, 9],
                 'compass': [4], 'magnetic-calibrated': [4],
                 'magnetic-uncalibrated': [2], 'magnetic-raw': [3], 'pressure': [5],
                 'proximity': [7], 'proximity-raw': [10],
                 'thermal': [34], 'rotation': [16, 17]}


def read_thermal_adc(probe, sensor_mask):
    # factory/thermistor.c:show_thermistor_channel{0,1}_ADC: READ two
    # unsigned bytes each, not the separate B3 threshold-write command.
    require_advertised([34], sensor_mask)
    result = {}
    for channel, command in ((0, 0xA9), (1, 0xAA)):
        data = probe.transaction(command, length=2)
        if len(data) != 2:
            raise RuntimeError('Invalid thermistor ADC reply length')
        result[str(channel)] = struct.unpack('<H', data)[0]
    return result


def read_magnetic_fuse(probe, sensor_mask):
    # Pinned magnetic_common.c:get_fuserom_data: cmd01, AP2HUB_READ, 3B.
    # This reads factory sensitivity data; it neither starts self-test nor
    # applies calibration. Never replace a missing/invalid reply with zeros.
    require_advertised([2], sensor_mask)
    values = tuple(probe.transaction(0x01, length=3))
    return {'bytes': list(values), 'valid_factory_bytes': all(v not in (0, 255) for v in values)}


def require_advertised(selected, sensor_mask):
    missing = [sensor for sensor in selected if not sensor_mask & (1 << sensor)]
    if missing:
        raise RuntimeError('Hub does not advertise selected sensors: ' + str(missing))


LIGHT_LAYOUTS = {'raw10': '<HHHHBB', 'lux18': '<IiHHHHBB', 'lux19': '<IiHHHHHB'}


def light_fields(values, layout):
    names = (['hub_lux', 'cct_k', 'red', 'green', 'blue', 'clear', 'integration_time', 'gain']
             if layout == 'lux18' else
             ['hub_lux', 'cct_k', 'red', 'green', 'blue', 'clear', 'gain', 'integration_time']
             if layout == 'lux19' else
             ['red', 'green', 'blue', 'clear', 'integration_time', 'gain'])
    return dict(zip(names, values))


def require_board():
    try:
        compatible = Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0')
    except OSError as error:
        raise SystemExit('Cannot verify the native star2lte board') from error
    if b'samsung,star2lte' not in compatible:
        raise SystemExit('Expected the native star2lte board')


def sampling_complete(selected, sensor_mask, samples):
    """A successful transaction is not evidence of an actual sensor sample."""
    return all(sensor_mask & (1 << sensor) and samples.get(sensor) for sensor in selected)


def summarize_samples(selected, samples):
    result = {}
    for sensor in selected:
        values = samples.get(sensor, [])
        result[str(sensor)] = {'count': len(values), 'first': values[0] if values else None,
            'min': [min(v[i] for v in values) for i in range(len(values[0]))] if values else None,
            'max': [max(v[i] for v in values) for i in range(len(values[0]))] if values else None}
    return result


def enable_sampling_phases(probe, selected, sensor_mask, enabled):
    """Count startup separately and retain only each sensor's post-enable data."""
    startup_counts = {}
    for sensor in selected:
        startup_counts[str(sensor)] = len(probe.samples.get(sensor, []))
        # Other sensors may report while earlier enable transactions are being
        # handled. Clear immediately before THIS sensor's A1, not only once.
        probe.samples[sensor] = []
        if not sensor_mask & (1 << sensor):
            continue
        enabled.append(sensor)
        probe.transaction(0xA1, struct.pack('<BiiB', sensor, 200, 0, 0))
    enable_samples = {sensor: list(probe.samples[sensor]) if sensor in enabled else []
                      for sensor in selected}
    for sensor in selected:
        probe.samples[sensor] = []
    return startup_counts, enable_samples


def require_hub(chip_id):
    if chip_id != 0x55:
        raise RuntimeError('Unexpected sensor hub identity; no sensor enabled')


def require_transport_ready():
    if Path('/sys/class/sec/sensorhub/ready').read_text().strip() != '1':
        raise RuntimeError('Hub transport not ready; no sensor enabled')


def settle_transport(probe, seconds):
    """Bounded receive-only settling; transport READY is not SSP readiness."""
    deadline = time.monotonic() + seconds
    while True:
        require_transport_ready()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        probe.pump(min(.1, remaining))


def acquire_hub_identity(probe):
    # Stock SSP waits for MCU init completion after ESW:READY. Do not enable a
    # sensor or send AP state until a real identity and metadata reply arrive.
    settle_transport(probe, 5)
    for attempt in range(3):
        require_transport_ready()
        try:
            chip = int.from_bytes(probe.transaction(0x0F, length=1), 'little')
        except RuntimeError as error:
            require_transport_ready()
            if str(error) != 'No valid sensor reply for command 0xf' or attempt == 2:
                raise
            # Preserve this Probe and its increasing sequence across retries.
            settle_transport(probe, 1)
            continue
        require_transport_ready()
        require_hub(chip)
        result = {'chip_id': chip}
        for name, command, size in [('firmware', 0xF0, 4), ('sensor_mask', 0xF4, 8)]:
            require_transport_ready()
            result[name] = int.from_bytes(probe.transaction(command, length=size), 'little')
            require_transport_ready()
        return result


def terminate_probe(signum, _frame):
    # A systemd RuntimeMax/stop uses SIGTERM. Raising lets the existing sensor
    # disable/fd cleanup run instead of silently leaving enabled sensors behind.
    raise SystemExit(128 + signum)


def disable_sensors(probe, enabled):
    """Try every cleanup even if one transaction fails; never report success."""
    errors = []
    for sensor in enabled:
        try:
            probe.transaction(0xA2, struct.pack('<Bi', sensor, 0))
        except (OSError, RuntimeError) as error:
            errors.append(sensor)
            print(json.dumps({'disable_failed': sensor, 'error': str(error)}), flush=True)
    if errors:
        raise RuntimeError('Sensor disable failed: ' + str(errors))


class Probe:
    def __init__(self, light_layout=None):
        self.fd = os.open('/dev/zrn_ssp', os.O_RDWR | os.O_NONBLOCK)
        self.outer = bytearray()
        self.inner = bytearray()
        self.sequence = 0
        self.pending = None
        self.reply = None
        self.formats = dict(SENSOR_FORMATS)
        if light_layout:
            self.formats[9] = LIGHT_LAYOUTS[light_layout]
        self.samples = {sensor: [] for sensor in self.formats}
        self.unparsed = 0

    def records(self, data):
        position = 0
        decoded = []
        while position < len(data):
            tag = data[position]; position += 1
            if tag == 0x37 and position < len(data):
                sensor = data[position]; position += 1
                if sensor not in self.formats:
                    self.unparsed += 1
                    return False
                size = struct.calcsize(self.formats[sensor])
                if position + size + 8 > len(data):
                    self.unparsed += 1
                    return False
                decoded.append((sensor, struct.unpack_from(self.formats[sensor], data, position)))
                position += size + 8
            elif tag == 0x03 and position + 2 <= len(data):
                size = struct.unpack_from('<H', data, position)[0]
                if size == 0 or position + 2 + size > len(data):
                    self.unparsed += 1
                    return False
                position += 2 + size
            elif tag in (0x0A, 0x06):
                continue
            elif tag == 0x05:
                if (position + 2 > len(data) or data[position] != 1 or
                        data[position + 1] >= 37):  # pinned SENSOR_MAX
                    self.unparsed += 1
                    return False
                position += 2
            else:
                self.unparsed += 1
                return False
        # An invalid trailing record must not leave a partially decoded packet
        # looking like a successful light-layout match.
        for sensor, values in decoded:
            self.samples[sensor].append(values)
        return True

    def pump(self, seconds):
        if not select.select([self.fd], [], [], seconds)[0]:
            return
        self.outer.extend(os.read(self.fd, 16384))
        while len(self.outer) >= 2:
            size = struct.unpack_from('<H', self.outer)[0]
            if len(self.outer) < size + 2:
                break
            self.inner.extend(self.outer[2:size + 2]); del self.outer[:size + 2]
        while len(self.inner) >= 4:
            options, size = struct.unpack_from('<HH', self.inner)
            kind = options & 3
            consumed = 4 if kind == 1 else 4 + size
            if len(self.inner) < consumed:
                break
            data = bytes(self.inner[4:consumed]); del self.inner[:consumed]
            if kind == 2:
                self.records(data)
            elif self.pending and options == self.pending[0]:
                if kind == 1:
                    payload = self.pending[1]
                    if payload and os.write(self.fd, payload) != len(payload):
                        raise RuntimeError('Short sensor payload write')
                    self.reply = b''
                else:
                    self.reply = data
            else:
                self.unparsed += 1

    def transaction(self, command, payload=b'', length=0):
        self.sequence = self.sequence % 8191 + 1
        options = self.sequence << 3 | (0 if length else 1)
        self.pending = (options, payload)
        self.reply = None
        request = struct.pack('<BHHI', command, length or len(payload), options, 0)
        if os.write(self.fd, request) != len(request):
            raise RuntimeError('Short sensor header write')
        deadline = time.monotonic() + 2
        while self.reply is None and time.monotonic() < deadline:
            self.pump(.05)
        self.pending = None
        if self.reply is None:
            raise RuntimeError(f'No valid sensor reply for command {command:#x}')
        if length and len(self.reply) != length:
            raise RuntimeError(f'Invalid sensor reply length for command {command:#x}')
        # Hub consumption of a write payload is not a second explicit reply.
        # Keep following headers apart instead of flooding its transport queue.
        if payload:
            until = time.monotonic() + .15
            while time.monotonic() < until:
                self.pump(.02)
        return self.reply

    def notify_ap_awake(self):
        """Experimental zero-length notifications, not reply transactions.

        Pinned ssp_send_cmd uses length0/AP2HUB_WRITE/data0. ssp_bbd's
        do_transfer explicitly marks these use_no_irq and does not add them
        to its pending-reply list. Do not manufacture an acknowledgement.
        """
        if self.pending is not None:
            raise RuntimeError('Cannot notify AP state during a pending transaction')
        for command in (0xD1, 0xD3):  # WAKEUP, RESUME only; never SLEEP/RESET
            header = struct.pack('<BHHI', command, 0, 1, 0)
            if os.write(self.fd, header) != len(header):
                raise RuntimeError('Short AP-awake notification write')
            until = time.monotonic() + .15
            while time.monotonic() < until:
                self.pump(.02)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample-seconds', type=int, default=0, choices=range(0, 61))
    parser.add_argument('--sensors', choices=SENSOR_GROUPS, default='motion')
    parser.add_argument('--light-layout', choices=LIGHT_LAYOUTS, help='Must match the own-device hub configuration')
    parser.add_argument('--read-thermal-adc', action='store_true',
                        help='Read two raw thermistor ADC channels; no thresholds, calibration or sensor enable')
    parser.add_argument('--read-magnetic-fuse', action='store_true',
                        help='Read three AKM factory sensitivity bytes; no calibration write or self-test')
    parser.add_argument('--stream', action='store_true', help='Print numeric samples once per second')
    parser.add_argument('--ap-awake', action='store_true',
                        help='Experimental volatile WAKEUP/RESUME notifications before bounded sampling; default off')
    args = parser.parse_args()
    require_board()
    selected = SENSOR_GROUPS[args.sensors]
    if 9 in selected and args.sample_seconds and not args.light_layout:
        parser.error('Select an explicit own-device light layout before sampling')
    if args.ap_awake and not args.sample_seconds:
        parser.error('--ap-awake requires a bounded sampling interval')
    if Path('/sys/class/sec/sensorhub/ready').read_text().strip() != '1':
        raise SystemExit('Hub not ready; start the own-device lhd with its stock configuration first')
    signal.signal(signal.SIGTERM, terminate_probe)
    with acquire_probe_lock():
        probe = Probe(args.light_layout)
        enabled = []
        complete = True
        try:
            result = acquire_hub_identity(probe)
            if args.read_thermal_adc:
                result['thermal_adc_raw'] = read_thermal_adc(probe, result['sensor_mask'])
            if args.read_magnetic_fuse:
                result['magnetic_fuse'] = read_magnetic_fuse(probe, result['sensor_mask'])
            if args.sample_seconds:
                require_advertised(selected, result['sensor_mask'])
                if args.ap_awake:
                    probe.notify_ap_awake()
                    result['ap_awake_notification'] = {'commands': [0xD1, 0xD3], 'acknowledged': False}
                startup_counts, enable_samples = enable_sampling_phases(
                    probe, selected, result['sensor_mask'], enabled)
                started = time.monotonic()
                deadline = started + args.sample_seconds
                next_report = started + 1
                while time.monotonic() < deadline:
                    probe.pump(.1)
                    if args.stream and time.monotonic() >= next_report:
                        values = probe.samples.get(9, [])
                        print(json.dumps({'elapsed_s': round(time.monotonic()-started, 1),
                            'sensor_counts': {str(sensor): len(probe.samples.get(sensor, [])) for sensor in selected},
                            'sensor_latest': {str(sensor): probe.samples[sensor][-1] if probe.samples.get(sensor) else None for sensor in selected},
                            'light_count': len(values), 'light': light_fields(values[-1], args.light_layout)
                            if values else None}), flush=True)
                        next_report += 1
                result['light_layout'] = args.light_layout
                result['startup_sample_counts'] = startup_counts
                result['enable_samples'] = summarize_samples(selected, enable_samples)
                result['samples'] = summarize_samples(selected, probe.samples)
                result['measurement_window_seconds'] = round(time.monotonic() - started, 3)
                result['sampling_window_complete'] = bool(sampling_complete(
                    selected, result['sensor_mask'], probe.samples))
                observations = {sensor: enable_samples[sensor] + probe.samples.get(sensor, [])
                                for sensor in selected}
                complete = bool(sampling_complete(selected, result['sensor_mask'], observations))
                result['sampling_complete'] = complete
            result['unparsed_frames'] = probe.unparsed
            print(json.dumps(result, indent=2))
        finally:
            try:
                disable_sensors(probe, enabled)
            finally:
                os.close(probe.fd)
        if not complete:
            raise SystemExit(2)


if __name__ == '__main__':
    main()

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
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import struct
import time


# Layout facts from the pinned Lineage sensor_value/get_light_sensordata.
# G965N reference config uses REPORT_LUX with one-byte gain (lux18).
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
        self.formats = {0: '<hhh', 1: '<iii'}
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
    parser.add_argument('--sensors', choices=['motion', 'light', 'all'], default='motion')
    parser.add_argument('--light-layout', choices=LIGHT_LAYOUTS, help='Must match the own-device hub configuration')
    parser.add_argument('--stream', action='store_true', help='Print numeric samples once per second')
    parser.add_argument('--ap-awake', action='store_true',
                        help='Experimental volatile WAKEUP/RESUME notifications before bounded sampling; default off')
    args = parser.parse_args()
    require_board()
    selected = [0, 1] if args.sensors == 'motion' else [9] if args.sensors == 'light' else [0, 1, 9]
    if 9 in selected and args.sample_seconds and not args.light_layout:
        parser.error('Select an explicit own-device light layout before sampling')
    if args.ap_awake and not args.sample_seconds:
        parser.error('--ap-awake requires a bounded sampling interval')
    if Path('/sys/class/sec/sensorhub/ready').read_text().strip() != '1':
        raise SystemExit('Hub not ready; start the own-device lhd with its stock configuration first')
    signal.signal(signal.SIGTERM, terminate_probe)
    with open('/run/lock/g965n-ssp-probe.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        probe = Probe(args.light_layout)
        enabled = []
        complete = True
        try:
            result = acquire_hub_identity(probe)
            if args.sample_seconds:
                if 9 in selected and not result['sensor_mask'] & (1 << 9):
                    raise RuntimeError('The hub does not advertise a light sensor')
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

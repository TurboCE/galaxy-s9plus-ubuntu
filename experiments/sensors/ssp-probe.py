#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read chip identity and optionally short accel/gyro samples from a ready hub.

Protocol fields/commands follow LineageOS's GPL Exynos9810 ssp.h/ssp_data.c
(commit 6a9461f9460ca51d1217e5069a5d5556fcc79e63). This is an original diagnostic
client, not a copy of a third-party userspace daemon. One transaction at a time;
no sleep/wake commands, calibration writes or persistent sensor settings.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import select
import struct
import time


class Probe:
    def __init__(self):
        self.fd = os.open('/dev/zrn_ssp', os.O_RDWR | os.O_NONBLOCK)
        self.outer = bytearray()
        self.inner = bytearray()
        self.sequence = 0
        self.pending = None
        self.reply = None
        self.samples = {0: [], 1: []}
        self.unparsed = 0

    def records(self, data):
        position = 0
        while position < len(data):
            tag = data[position]; position += 1
            if tag == 0x37 and position < len(data):
                sensor = data[position]; position += 1
                formats = {0: '<hhh', 1: '<iii'}
                if sensor not in formats:
                    break
                size = struct.calcsize(formats[sensor])
                if position + size + 8 > len(data):
                    break
                self.samples[sensor].append(struct.unpack_from(formats[sensor], data, position))
                position += size + 8
            elif tag == 0x03 and position + 2 <= len(data):
                size = struct.unpack_from('<H', data, position)[0]
                position += 2 + size
            elif tag in (0x0A, 0x06):
                continue
            elif tag == 0x05:
                position += 2
            else:
                self.unparsed += 1
                break

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
        if self.reply is None or (length and len(self.reply) != length):
            raise RuntimeError(f'No valid sensor reply for command {command:#x}')
        # Hub consumption of a write payload is not a second explicit reply.
        # Keep following headers apart instead of flooding its transport queue.
        if payload:
            until = time.monotonic() + .15
            while time.monotonic() < until:
                self.pump(.02)
        return self.reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample-seconds', type=int, default=0, choices=range(0, 11))
    args = parser.parse_args()
    if Path('/sys/class/sec/sensorhub/ready').read_text().strip() != '1':
        raise SystemExit('Hub not ready; start the own-device lhd with its stock configuration first')
    with open('/run/lock/g965n-ssp-probe.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        probe = Probe()
        enabled = []
        try:
            result = {name: int.from_bytes(probe.transaction(cmd, length=size), 'little')
                      for name, cmd, size in [('chip_id', 0x0F, 1), ('firmware', 0xF0, 4), ('sensor_mask', 0xF4, 8)]}
            if args.sample_seconds:
                for sensor in (0, 1):
                    if not result['sensor_mask'] & (1 << sensor):
                        continue
                    probe.transaction(0xA1, struct.pack('<BiiB', sensor, 200, 0, 0))
                    enabled.append(sensor)
                deadline = time.monotonic() + args.sample_seconds
                while time.monotonic() < deadline:
                    probe.pump(.1)
                result['samples'] = {str(sensor): {'count': len(values),
                    'first': values[0] if values else None,
                    'min': [min(v[i] for v in values) for i in range(3)] if values else None,
                    'max': [max(v[i] for v in values) for i in range(3)] if values else None}
                    for sensor, values in probe.samples.items()}
            result['unparsed_frames'] = probe.unparsed
            print(json.dumps(result, indent=2))
        finally:
            try:
                for sensor in enabled:
                    probe.transaction(0xA2, struct.pack('<Bi', sensor, 0))
            finally:
                os.close(probe.fd)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""On-device checks for the G965N RTC trial, as root while the phone is awake."""
import os
import datetime
from pathlib import Path
import select
import struct
import time

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

require(os.geteuid() == 0, 'Root is required for the bounded RTC alarm check')
base = Path('/sys/class/rtc/rtc0')
node = Path('/dev/rtc0')
require(node.is_char_device(), 'No native RTC character device')
require((base / 'hctosys').read_text().strip() == '0', 'Expected system clock isolation')
require((base / 'device/of_node/compatible').read_bytes().split(b'\0')[0] == b'samsung,exynos8-rtc', 'Unexpected RTC compatible')
clock_start = time.clock_gettime(time.CLOCK_REALTIME) - time.monotonic()
stamp = lambda: int((base / 'since_epoch').read_text().strip())
earlier = stamp()
time.sleep(2.2)
elapsed = stamp() - earlier
require(1 <= elapsed <= 4, f'RTC counter did not advance as expected: {elapsed}')
print('RTC device registered; native counter advances; HCTOSYS disabled', flush=True)
print('RTC date valid:', 2000 <= datetime.datetime.fromtimestamp(earlier, datetime.timezone.utc).year < 2100, flush=True)
alarm = base / 'wakealarm'
if not alarm.is_file():
    raise RuntimeError('Driver has no standard wakealarm attribute')
if alarm.read_text().strip():
    raise RuntimeError('Existing RTC alarm preserved')
with node.open('rb', buffering=0) as rtc:
    try:
        alarm.write_text('+4\n')
        poll = select.poll()
        poll.register(rtc, select.POLLIN)
        if not poll.poll(8500):
            raise RuntimeError('RTC alarm IRQ did not reach /dev/rtc0')
        (event,) = struct.unpack('@L', rtc.read(struct.calcsize('@L')))
        require(event & 0x20 and event >> 8, f'Missing RTC_AF: {event}')
        print('Awake RTC alarm interrupt delivered', flush=True)
    finally:
        if alarm.read_text().strip():
            alarm.write_text('0\n')
        require(not alarm.read_text().strip(), 'Trial wakealarm left armed')
require(abs(time.clock_gettime(time.CLOCK_REALTIME) - time.monotonic() - clock_start) < 2, 'System clock changed during the alarm trial')
print('System clock remained monotonic through the trial; no alarm left armed', flush=True)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Short quiet speaker-to-microphone correlation test. No recording is retained.

Requires the reviewed ABOX module with capture=1, ALSA tools and no other PCM
client. Produces two quiet tones at minimum amplifier gain, records five
seconds, and reports aggregate measurements only. Not a speech-quality test.
"""
import argparse
import array
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

RATE = 48000


def power(samples, frequency):
    coefficient = 2 * math.cos(2 * math.pi * frequency / RATE)
    a = b = 0.0
    for sample in samples:
        value = sample + coefficient * a - b
        b, a = a, value
    return max(0, a * a + b * b - coefficient * a * b) / len(samples) ** 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-low-volume-test', action='store_true', required=True)
    parser.parse_args()
    os.umask(0o077)
    subprocess.run(['amixer', '-c0', 'sset', 'Speaker', '0'], check=True, stdout=subprocess.DEVNULL)
    with tempfile.TemporaryDirectory(prefix='g965n-audio-') as folder:
        folder = Path(folder)
        tone, recording = folder / 'tone.raw', folder / 'capture.raw'
        samples = array.array('h')
        for frame in range(3 * RATE):
            t = frame / RATE
            frequency = 700 if .5 <= t < 1.25 else 1300 if 1.75 <= t < 2.5 else 0
            value = int(1024 * math.sin(2 * math.pi * frequency * t)) if frequency else 0
            samples.extend((value, value))
        tone.write_bytes(samples.tobytes())
        capture = subprocess.Popen(['arecord', '-q', '-D', 'hw:0,2', '-t', 'raw', '-f', 'S16_LE',
                                    '-c2', '-r48000', '-d5', str(recording)])
        try:
            time.sleep(.6)
            subprocess.run(['aplay', '-q', '-D', 'hw:0,0', '-t', 'raw', '-f', 'S16_LE',
                            '-c2', '-r48000', str(tone)], check=True, timeout=10)
            if capture.wait(timeout=10):
                raise RuntimeError('Capture failed')
        finally:
            if capture.poll() is None:
                capture.terminate()
                capture.wait(timeout=5)
        raw = array.array('h'); raw.frombytes(recording.read_bytes())
        if len(raw) != RATE * 5 * 2:
            raise RuntimeError('Unexpected capture size')
        result = []
        for channel in (0, 1):
            data = raw[channel::2]
            windows = [data[i:i + RATE // 4] for i in range(0, len(data), RATE // 4)]
            energies = [[power(w, f) for f in (700, 1300)] for w in windows]
            result.append({'channel': channel, 'samples': len(data),
                           'rms': round(math.sqrt(sum(v * v for v in data) / len(data)), 2),
                           'peak': max(abs(v) for v in data),
                           'tone_power_by_quarter_second': [[round(p, 2) for p in row] for row in energies]})
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

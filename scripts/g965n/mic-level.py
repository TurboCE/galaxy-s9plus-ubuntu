#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Measure Pulse microphone levels without saving audio; speak during the run.

Numeric activity alone is not proof of intelligible speech or app recognition.
"""
import argparse
import array
import math
import os
import select
import subprocess
import time
import json


def stats(samples):
    left, right = samples[::2], samples[1::2]
    pairs = min(len(left), len(right))
    left, right = left[:pairs], right[:pairs]
    le = sum(x*x for x in left); re = sum(x*x for x in right)
    lr = sum(x*y for x, y in zip(left, right))
    mono = sum(((x+y)/2)**2 for x, y in zip(left, right))
    return {'frames': pairs, 'peak': max(map(abs, samples), default=0),
            'rms_left': round(math.sqrt(le/pairs), 1) if pairs else 0,
            'rms_right': round(math.sqrt(re/pairs), 1) if pairs else 0,
            'rms_mono': round(math.sqrt(mono/pairs), 1) if pairs else 0,
            'correlation': round(lr/math.sqrt(le*re), 3) if le and re else None,
            'clipped_samples': sum(abs(x) >= 32760 for x in samples)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds', type=int, choices=range(1, 61), default=15)
    p.add_argument('--source', default='@DEFAULT_SOURCE@')
    a = p.parse_args()
    child = subprocess.Popen(['parec', '--device='+a.source, '--format=s16le',
        '--rate=48000', '--channels=2', '--raw'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic()+a.seconds; mark = time.monotonic()
    samples = []; total = 0; pending = b''
    try:
        while time.monotonic() < deadline:
            if select.select([child.stdout], [], [], .2)[0]:
                data = os.read(child.stdout.fileno(), 32768)
                if not data:
                    break
                total += len(data); data = pending + data
                count = len(data)//4*4
                block = array.array('h'); block.frombytes(data[:count])
                pending = data[count:]; samples.extend(block)
            if time.monotonic()-mark >= 1:
                print(json.dumps(stats(samples)), flush=True)
                samples = []; mark = time.monotonic()
        if samples:
            print(json.dumps(stats(samples)), flush=True)
    finally:
        child.terminate()
        try:
            child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait()
        print(json.dumps({'total_bytes': total, 'error': child.stderr.read().decode(errors='replace')[:300]}), flush=True)
    raise SystemExit(0 if total else 1)


if __name__ == '__main__':
    main()

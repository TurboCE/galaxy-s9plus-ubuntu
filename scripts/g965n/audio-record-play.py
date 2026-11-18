#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit short microphone recording/playback test. Files stay private.

Playback twice: original then bounded normalization. Delete temporary recordings
once the owner has judged speech; neither signal levels nor playback imply ASR success.
"""
import argparse
import array
import json
import fcntl
import math
import os
from pathlib import Path
import select
import subprocess
import time
import wave


def wav(path, data):
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(48000)
        out.writeframes(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--record-play', action='store_true', required=True)
    p.add_argument('--seconds', type=int, choices=range(3, 21), default=10)
    p.add_argument('--start-delay', type=int, choices=range(2, 31), default=5)
    p.add_argument('--cue', action='store_true', help='Play a quiet cue before capture')
    a = p.parse_args()
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected native star2lte')
    os.umask(0o077)
    lock = open(Path('/run/user') / str(os.getuid()) / 'g965n-audio-test.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    directory = Path('/run/user') / str(os.getuid()) / ('g965n-mic-test-' + str(time.time_ns()))
    directory.mkdir(mode=0o700)
    print(f'Recording starts in {a.start_delay} seconds; speak after the cue if enabled.', flush=True)
    time.sleep(a.start_delay)
    if a.cue:
        cue = directory / 'cue.wav'
        samples = array.array('h', (round(1000*math.sin(2*math.pi*750*i/48000)*
            min(1, i/240, (9600-i)/240)) for i in range(9600)))
        wav(cue, samples.tobytes())
        try:
            subprocess.run(['paplay', str(cue)], check=True, timeout=5)
        finally:
            cue.unlink(missing_ok=True)
        time.sleep(.7)
    proc = subprocess.Popen(['parec', '--device=@DEFAULT_SOURCE@', '--format=s16le',
        '--rate=48000', '--channels=1', '--raw'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    audio = bytearray(); discard = 24000*2; wanted = a.seconds*48000*2
    deadline = time.monotonic()+a.seconds+10
    try:
        while len(audio) < wanted and time.monotonic() < deadline:
            if not select.select([proc.stdout], [], [], .2)[0]:
                continue
            data = os.read(proc.stdout.fileno(), 16384)
            if not data:
                break
            skip = min(discard, len(data)); discard -= skip; data = data[skip:]
            audio.extend(data[:wanted-len(audio)])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait()
    if len(audio) != wanted:
        raise RuntimeError('Incomplete capture; no success claim: ' + proc.stderr.read().decode(errors='replace')[:200])
    original = directory / 'original.wav'; normalized = directory / 'normalized.wav'
    wav(original, audio)
    samples = array.array('h'); samples.frombytes(audio)
    peak = max(map(abs, samples), default=0)
    gain = min(16.0, 6553.0/peak) if peak else 1.0
    adjusted = array.array('h', (max(-32768, min(32767, round(x*gain))) for x in samples))
    wav(normalized, adjusted.tobytes())
    print(json.dumps({'directory': str(directory), 'peak': peak,
        'rms': round(math.sqrt(sum(x*x for x in samples)/len(samples)), 1),
        'normalization_gain': round(gain, 2), 'seconds': a.seconds}), flush=True)
    # Prevent the replay from being fed straight back into an open voice app.
    outputs = json.loads(subprocess.check_output(['pactl','--format=json','list','source-outputs'], text=True))
    muted = []
    try:
        for stream in outputs:
            if stream.get('properties', {}).get('application.name') == 'Chromium input':
                muted.append((str(stream['index']), bool(stream.get('mute'))))
                subprocess.run(['pactl','set-source-output-mute',str(stream['index']),'1'], check=True)
        for label, path in [('original', original), ('normalized', normalized)]:
            print('PLAYBACK_' + label, flush=True)
            subprocess.run(['paplay', '--device=@DEFAULT_SINK@', str(path)], check=True, timeout=a.seconds+10)
            time.sleep(1)
    finally:
        for index, mute in muted:
            subprocess.run(['pactl','set-source-output-mute',index,'1' if mute else '0'], capture_output=True)
    print('PLAYBACK_COMPLETE; recordings remain private until owner confirmation, then delete them.', flush=True)


if __name__ == '__main__':
    main()

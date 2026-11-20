#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded GeoClue-source check; never print or store coordinates/NMEA."""
import argparse
import collections
import json
import os
from pathlib import Path
import select
import signal
import socket
import time

STOP = False


def sentence(line):
    try:
        text = line.decode('ascii').strip()
        body, checksum = text[1:].rsplit('*', 1)
        if not text.startswith('$') or len(checksum) != 2:
            return None
        value = 0
        for char in body:
            value ^= ord(char)
        if value != int(checksum, 16):
            return None
        return body.split(',')
    except (UnicodeError, ValueError):
        return None


def coordinates_present(fields, lat, ns, lon, ew):
    try:
        a, b = float(fields[lat]), float(fields[lon])
        return (0 <= a <= 9000 and 0 <= b <= 18000 and
                a % 100 < 60 and b % 100 < 60 and
                fields[ns] in ('N', 'S') and fields[ew] in ('E', 'W'))
    except (IndexError, ValueError):
        return False


def collect(peer, seconds, summary=None):
    started = time.monotonic()
    deadline = started + seconds
    report = started
    buffer = b''
    counts = collections.Counter()
    state = {'valid_sentences': 0, 'invalid_sentences': 0,
             'satellites_in_view_max': 0, 'satellites_used_max': 0,
             'gsa_fix_type_max': 0, 'fix_observed': False}

    def emit(final=False):
        payload = {'elapsed_seconds': round(time.monotonic() - started),
                   'updated_at': time.time(), 'final': final, **state,
                   'sentence_types': dict(counts)}
        text = json.dumps(payload)
        if summary:
            temporary = summary.with_suffix('.tmp')
            with temporary.open('w') as stream:
                os.chmod(temporary, 0o644)
                stream.write(text + '\n')
            temporary.replace(summary)
        print(text, flush=True)

    while time.monotonic() < deadline and not STOP:
        if select.select([peer], [], [], min(1, max(0, deadline - time.monotonic())))[0]:
            chunk = peer.recv(4096)
            if not chunk:
                state['source_closed'] = True
                break
            buffer += chunk
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                fields = sentence(line)
                if not fields:
                    state['invalid_sentences'] += 1
                    continue
                state['valid_sentences'] += 1
                kind = fields[0][-3:]
                counts[kind] += 1
                try:
                    if kind == 'GGA':
                        state['satellites_used_max'] = max(state['satellites_used_max'], int(fields[7]))
                        if int(fields[6]) > 0 and coordinates_present(fields, 2, 3, 4, 5):
                            state['fix_observed'] = True
                    elif kind == 'RMC' and fields[2] == 'A' and coordinates_present(fields, 3, 4, 5, 6):
                        state['fix_observed'] = True
                    elif kind == 'GSV':
                        state['satellites_in_view_max'] = max(state['satellites_in_view_max'], int(fields[3]))
                    elif kind == 'GSA':
                        state['gsa_fix_type_max'] = max(state['gsa_fix_type_max'], int(fields[2]))
                except (IndexError, ValueError):
                    state['invalid_sentences'] += 1
            if len(buffer) > 16384:
                buffer = b''
                state['invalid_sentences'] += 1
        if time.monotonic() >= report:
            emit()
            report = time.monotonic() + 15
    if STOP:
        state['cancelled'] = True
    emit(final=True)
    return state['fix_observed']


if __name__ == '__main__':
    def stop(signum, frame):
        global STOP
        STOP = True
    signal.signal(signal.SIGTERM, stop)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=180)
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    if not 15 <= args.seconds <= 900:
        parser.error('--seconds must be between 15 and 900')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
        peer.settimeout(10)
        peer.connect('/run/g965n-gnss/nmea.sock')
        peer.settimeout(None)
        raise SystemExit(0 if collect(peer, args.seconds, args.summary) else 2)

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only aggregate PGLOR status; never emit NMEA, coordinates or IDs.

The common STA prefix is inferred from published chipset-supplier messages,
not a qualified Samsung version9 specification. Does not activate GNSS.
"""
import argparse
import collections
import json
import math
import re
import socket
import time

class ReceiverStatus:
    def __init__(self):
        self.types = collections.Counter()
        self.versions = collections.Counter()
        self.layouts = 0
        self.ranges = {}
        self.flags = collections.Counter()
        self.time_sources = set()
        self.power_modes = set()

    def add_range(self, name, value):
        if name not in self.ranges:
            self.ranges[name] = [value, value]
        else:
            self.ranges[name][0] = min(self.ranges[name][0], value)
            self.ranges[name][1] = max(self.ranges[name][1], value)

    def feed(self, sentence):
        if not sentence.startswith(b'$PGLOR,') or len(sentence) > 256:
            return
        body, sep, checksum = sentence.rstrip(b'\r\n').partition(b'*')
        if not sep or not re.fullmatch(b'[0-9A-Fa-f]{2}', checksum):
            return
        calculated = 0
        for byte in body[1:]:
            calculated ^= byte
        if calculated != int(checksum, 16):
            return
        try:
            fields = body.decode('ascii').split(',')
        except UnicodeError:
            return
        if len(fields) < 3 or not re.fullmatch(r'[0-9]{1,3}', fields[1]):
            return
        kind = fields[2] if fields[2] in ('STA','UNC','SAT','PWR','AGC','FIX') else 'OTHER'
        self.types[kind] += 1
        self.versions[fields[1]] += 1
        if kind != 'STA' or fields[1] not in ('6','9','10') or len(fields) < 25:
            return
        if not all(fields[i] == value for i, value in ((10,'P'),(12,'L'),(14,'C'),(16,'S'),(20,'R'))):
            return
        self.layouts += 1
        # Only nonlocation numeric prefix fields; never export the whole record.
        for i in range(4,10):
            try:
                value = float(fields[i])
            except ValueError:
                continue
            if math.isfinite(value):
                self.add_range('sta_field_' + str(i), value)
        if re.fullmatch(r'[tT][pP][eE][fF]', fields[22]):
            self.flags[fields[22]] += 1
        if fields[19] in ('0','1','2','3','4','5'):
            self.time_sources.add(int(fields[19]))
        if fields[11] in ('D','F','S','H'):
            self.power_modes.add(fields[11])
        if re.fullmatch(r'[0-9]{1,3}', fields[23]) and int(fields[23]) <= 256:
            self.add_range('satellite_ephemeris_count', int(fields[23]))

    def summary(self):
        return {'pglor_types':dict(self.types), 'versions':dict(self.versions),
                'common_sta_prefix_records':self.layouts, 'numeric_ranges':self.ranges,
                'aid_flags':dict(self.flags), 'time_source_codes':sorted(self.time_sources),
                'power_mode_codes':sorted(self.power_modes),
                'interpretation':'common-prefix inference; Samsung layout not independently qualified'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=45)
    args = parser.parse_args()
    if not 10 <= args.seconds <= 300:
        parser.error('10..300 seconds required')
    status = ReceiverStatus()
    end = time.monotonic() + args.seconds
    pending = b''
    with socket.create_connection(('127.0.0.1',2948),timeout=3) as stream:
        stream.sendall(b'?WATCH={"enable":true,"raw":1,"json":false};\n')
        stream.settimeout(2)
        while time.monotonic() < end:
            try:
                data = stream.recv(65536)
            except socket.timeout:
                continue
            if not data:
                break
            pending += data
            if len(pending) > 262144:
                raise RuntimeError('Oversized receiver record')
            while b'\n' in pending:
                line,pending = pending.split(b'\n',1)
                status.feed(line)
    print(json.dumps(status.summary()))

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Diagnostic wired thermistor conversion; never controls charging.

Calibration: pinned Samsung rev26 DTS in REFERENCE.json. Owner's original
wired tables match. No calibration is provided for channel 11 (battery divider).
"""
import argparse
import json
from pathlib import Path

ADC = (275, 336, 415, 483, 551, 667, 764, 903, 1054, 1189, 1384,
       1575, 1787, 2042, 2263, 2492, 2723, 2937, 3127, 3309, 3463,
       3578, 3678)
TEMPERATURE = tuple(range(900, -201, -50))  # deci-degrees Celsius
CHANNELS = {'4': 'battery', '1': 'usb', '3': 'charger'}


def convert(raw):
    """Match sec_adc.c signed integer interpolation inside its valid domain.

    Unlike Android's endpoint clamping, reject out-of-table ADC values: an
    open/short/error must not masquerade as a valid extreme temperature.
    """
    if type(raw) is not int or not ADC[0] <= raw <= ADC[-1]:
        raise ValueError('Thermistor sample outside calibrated domain')
    for i, value in enumerate(ADC):
        if raw == value:
            return TEMPERATURE[i]
        if raw < value:
            # C signed division truncates toward zero, unlike Python //.
            drop = ((TEMPERATURE[i-1] - TEMPERATURE[i]) *
                    (raw - ADC[i-1])) // (value - ADC[i-1])
            return TEMPERATURE[i-1] - drop
    raise AssertionError('Unreachable calibration interval')


def summarize(rows):
    """Validate a fresh bounded five-sample capture, then trim min/max.

    This consumes a completed diagnostic receipt, not a live thermal service.
    It cannot establish current temperature or authorize charging later.
    """
    if len(rows) != 5:
        raise ValueError('Exactly five samples required')
    times = [r['monotonic_ns'] for r in rows]
    if (any(type(t) is not int for t in times) or
            any(b <= a for a, b in zip(times, times[1:])) or
            times[-1] - times[0] > 5_000_000_000):
        raise ValueError('Invalid, stale or non-monotonic capture')
    result = {}
    for channel, name in CHANNELS.items():
        values = [r[channel] for r in rows]
        for value in values:
            convert(value)  # Reject even a trimmed-out invalid reading.
        values.sort()
        trimmed_adc = sum(values[1:-1]) // 3
        result[name] = {'trimmed_adc': trimmed_adc,
                        'temperature_deci_c': convert(trimmed_adc)}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', type=Path, help='Private samples.json; never commit')
    args = parser.parse_args()
    print(json.dumps(summarize(json.loads(args.receipt.read_text()))))

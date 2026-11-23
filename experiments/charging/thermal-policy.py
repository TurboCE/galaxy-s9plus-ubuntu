#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Shadow thermal gates from pinned wired stock policy; no charging writes.

This is a subset for comparison, not a complete sec-battery implementation.
Swelling changes voltage/current/recharge rules upstream; a flag here must not
be turned into a guessed auto-enable or unconditional charge-stop policy.
"""

class ThermalPolicy:
    def __init__(self):
        self.hot = self.cold = self.usb_hot = self.swelling_hot = False

    def evaluate(self, temperatures):
        try:
            battery = temperatures['battery']['temperature_deci_c']
            usb = temperatures['usb']['temperature_deci_c']
            charger = temperatures['charger']['temperature_deci_c']
            if any(type(v) is not int or not -200 <= v <= 900 for v in (battery,usb,charger)):
                raise ValueError('Invalid calibrated temperature')
        except (KeyError,TypeError,ValueError):
            # Do not clear latched protections from a missing/error sample.
            return {'valid':False,'thermal_charge_permission':None,
                    'reason':'fresh calibrated battery/USB/charger temperature required'}
        self.hot = battery > 450 if self.hot else battery >= 500
        self.cold = battery < 50 if self.cold else battery <= 0
        self.usb_hot = usb > 750 if self.usb_hot else usb >= 800
        self.swelling_hot = battery > 390 if self.swelling_hot else battery >= 410
        return {'valid':True,'thermal_charge_permission':not (self.hot or self.cold or self.usb_hot),
                'battery_hot':self.hot,'battery_cold':self.cold,'usb_hot':self.usb_hot,
                'swelling_high_temperature_policy_required':self.swelling_hot,
                'mode':'shadow-only; full/recharge/swelling/current/time policy incomplete'}

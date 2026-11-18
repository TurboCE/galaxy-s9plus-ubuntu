# SPDX-License-Identifier: GPL-2.0-only
"""Reference protocol vectors are not a qualified S9 activation implementation."""
import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ril_reference_test', ROOT/'experiments/modem/ril-lab.py')
ril = importlib.util.module_from_spec(spec); spec.loader.exec_module(ril)


def ack(command, result=0x8000, kind=3):
    return struct.pack('<BBBH', command >> 8, command & 255, kind, result)


def ip():
    return bytes((1, 0, 0, 10, 20, 30, 40, 1, 1, 1, 1, 8, 8, 8, 8)) + bytes(12)


class ReferencePDPTests(unittest.TestCase):
    def test_source_layouts_and_no_credentials(self):
        body = ril.reference_define_pdp('fixture.apn')
        self.assertEqual(len(body), 127)
        self.assertEqual(body[:3], bytes((1, 1, 2)))
        self.assertEqual(body[3:14], b'fixture.apn')
        self.assertEqual(body[14:], bytes(113))
        self.assertEqual(ril.reference_activate_pdp(), bytes((1, 1)) + bytes(101))
        self.assertEqual(ril.reference_activate_pdp(enable=False), bytes((0, 1)) + bytes(101))
        for apn in ('', 'bad\nAT', 'a'*101, '\x00'):
            with self.assertRaises(ValueError): ril.reference_define_pdp(apn)
        for cid in (0, 4, True, -1):
            with self.assertRaises(ValueError): ril.reference_activate_pdp(cid)

    def test_successful_reference_ack_status_ip_is_only_candidate(self):
        p = ril.ReferencePDPPlan('fixture.apn', 0)
        self.assertEqual(p.registered(1)[0], 0x0d01)
        self.assertIsNone(p.registered(2))
        self.assertIsNone(p.ack(ack(0x0d04), 2))
        self.assertIsNone(p.ack(ack(0x0d01, kind=2), 2))
        self.assertEqual(p.ack(ack(0x0d01), 3), (0x0d04, ril.reference_activate_pdp()))
        p.event(0x0d09, ip(), 4)
        p.event(0x0d10, bytes((1, 1, 0, 0)), 5)
        self.assertEqual(p.state, 'activate-pending')
        p.ack(ack(0x0d04), 6)
        self.assertEqual(p.state, 'candidate-ip')
        self.assertEqual(p.configuration['ipv4'], '10.20.30.40')
        self.assertEqual(p.configuration['dns'], ['1.1.1.1', '8.8.8.8'])
        self.assertNotIn('internet', p.state)

    def test_rejection_timeout_and_disabled_never_activate_again(self):
        p = ril.ReferencePDPPlan('fixture.apn', 0)
        p.registered(1); p.ack(ack(0x0d01, 0x8001), 2)
        self.assertEqual(p.state, 'failed')
        self.assertIsNone(p.registered(3))
        p = ril.ReferencePDPPlan('fixture.apn', 0, timeout=10)
        p.registered(1)
        self.assertIsNone(p.ack(ack(0x0d01), 10))
        self.assertEqual(p.state, 'failed')
        p = ril.ReferencePDPPlan('fixture.apn', 0)
        p.registered(1); p.ack(ack(0x0d01), 2)
        p.event(0x0d10, bytes((1, 3, 0, 0)), 3)
        self.assertEqual(p.state, 'failed')  # reference status3 means disabled

    def test_target_layouts_and_unusable_addresses_rejected(self):
        for body in (bytes(257), bytes(26), bytes(28), bytes((2,))+ip()[1:], bytes((1,0,1))+ip()[3:]):
            with self.assertRaises(ValueError): ril.reference_ip_config(body)
        for address in (bytes(4), bytes((127,0,0,1)), bytes((224,0,0,1)), bytes((169,254,1,1)), b'\xff'*4):
            with self.assertRaises(ValueError): ril.reference_ip_config(ip()[:3]+address+ip()[7:])
        with self.assertRaisesRegex(RuntimeError, 'blocked'):
            ril.require_qualified_s9_pdp()


if __name__ == '__main__': unittest.main()

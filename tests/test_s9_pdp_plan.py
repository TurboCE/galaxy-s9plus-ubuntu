# SPDX-License-Identifier: GPL-2.0-only
"""Independent synthetic vectors for owner-stock IpcProtocol41 wire facts."""
import importlib.util
import ipaddress
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('s9_pdp_test',ROOT/'experiments/modem/ril-lab.py')
ril=importlib.util.module_from_spec(spec);spec.loader.exec_module(ril)


def ack(command,result=0x8000,kind=3):
    return struct.pack('<BBBH',command>>8,command&255,kind,result)


def ipv4(size=157,flags=1|8|16|8192):
    body=bytearray(size);body[0]=1;struct.pack_into('<H',body,1,flags)
    for offset,value in ((3,'100.64.1.2'),(7,'1.1.1.1'),(11,'8.8.8.8'),(15,'100.64.1.1'),(19,'255.255.255.0')):
        body[offset:offset+4]=ipaddress.IPv4Address(value).packed
    struct.pack_into('<I',body,152,1500)
    return body


def status(state=1,cause=0,throttle=0):
    return struct.pack('<BBBBBI',1,state,cause,1,0,throttle)


class S9PDPTests(unittest.TestCase):
    def test_typed_wwan_queries_return_only_validated_status(self):
        self.assertEqual(ril.wwan_query_result('AT+CEREG?',
                         b'AT+CEREG?\r\r\n+CEREG: 0,1,"ABCD","ABCDEF",7\r\nOK\r\n'),
                         {'registration_code': 1})
        self.assertEqual(ril.wwan_query_result('AT+CGATT?',
                         b'AT+CGATT?\r\r\n+CGATT: 1\r\nOK\r\n'),
                         {'packet_attached': True})
        self.assertEqual(ril.wwan_query_result('AT+CSQ', b'\r\n+CSQ: 25,99\r\nOK\r\n'),
                         {'signal_rssi_code': 25})
        self.assertIn('error', ril.wwan_query_result('AT+CSQ', b'\r\n+CSQ: 42,99\r\nOK\r\n'))
        self.assertIn('error', ril.wwan_query_result('AT+CEREG?', b'\r\nERROR\r\n'))

    def test_independent_s9_builders_exact_source_fields(self):
        define=ril.s9_define_pdp('fixture.apn')
        self.assertEqual(len(define),127)
        self.assertEqual(define[:3],bytes((1,1,2)))
        self.assertEqual(define[3:104],b'fixture.apn'+bytes(90))
        self.assertEqual(define[104:],bytes(23))
        active=ril.s9_activate_pdp()
        self.assertEqual(len(active),105)
        self.assertEqual(active,bytes((1,1))+bytes(103))
        self.assertEqual(struct.unpack_from('<I',active,2)[0],0)
        self.assertEqual(active[6:38],bytes(32))
        self.assertEqual(active[38:70],bytes(32))
        self.assertEqual(active[102:105],bytes(3))
        self.assertEqual(ril.s9_activate_pdp(enable=False),bytes((0,1))+bytes(103))
        self.assertNotEqual(len(active),len(ril.reference_activate_pdp()))
        self.assertEqual(ril.s9_define_pdp('a'*100)[103],0)
        for apn in ('',None,'a'*101,'bad;AT','bad\0apn','bad\napn'):
            with self.assertRaises(ValueError):ril.s9_define_pdp(apn)
        for cid in (0,4,-1,True):
            with self.assertRaises(ValueError):ril.s9_activate_pdp(cid)

    def test_base_ipv4_has_supplied_metadata_and_preserves_unknown(self):
        body=ipv4(flags=1|8|16|8192|4|16384);body[156]=0x7f
        value=ril.s9_ip_config(body)
        self.assertEqual(value['ipv4'],'100.64.1.2')
        self.assertEqual(value['dns4'],['1.1.1.1','8.8.8.8'])
        self.assertEqual(value['gateway'],'100.64.1.1')
        self.assertEqual(value['prefix4'],24)
        self.assertEqual(value['mtu'],1500)
        self.assertEqual(value['gateway_source'],'modem-supplied')
        self.assertEqual(value['unknown_flags'],4)
        self.assertEqual(value['pco_raw'],127)
        self.assertEqual(value['raw_hex'],body.hex())
        self.assertEqual(len(value['pcscf4_raw']),3)

    def test_no_invented_gateway_or_mask_dns_zeros_filtered(self):
        body=ipv4(flags=1);body[7:15]=bytes(8)
        value=ril.s9_ip_config(body)
        self.assertIsNone(value['gateway']);self.assertIsNone(value['prefix4'])
        self.assertEqual(value['gateway_source'],'not-provided')
        self.assertEqual(value['prefix_source'],'not-provided')
        self.assertEqual(value['dns4'],[])
        self.assertIsNone(value['mtu'])

    def test_dual_stack_and_extended_pcscf_offsets(self):
        body=ipv4(257,1|64|8192)
        body[35:51]=ipaddress.IPv6Address('2001:db8::5').packed
        body[99:115]=ipaddress.IPv6Address('2001:4860:4860::8888').packed
        body[115:131]=ipaddress.IPv6Address('2606:4700:4700::1111').packed
        body[157:161]=ipaddress.IPv4Address('192.0.2.10').packed
        body[173:177]=ipaddress.IPv4Address('192.0.2.14').packed
        body[177:193]=ipaddress.IPv6Address('2001:db8::10').packed
        body[241:257]=ipaddress.IPv6Address('2001:db8::14').packed
        value=ril.s9_ip_config(body)
        self.assertEqual(value['ipv6'],'2001:db8::5')
        self.assertEqual(len(value['dns6']),2)
        self.assertEqual(len(value['pcscf4_raw']),8)
        self.assertEqual(value['pcscf4_raw'][3],'192.0.2.10')
        self.assertEqual(value['pcscf4_raw'][7],'192.0.2.14')
        self.assertEqual(value['pcscf6_raw'][3],'2001:db8::10')
        self.assertEqual(value['pcscf6_raw'][7],'2001:db8::14')

    def test_all_unqualified_lengths_and_wrong_cid_rejected(self):
        for size in range(300):
            if size not in (157,257):
                with self.assertRaises(ValueError,msg=str(size)):ril.s9_ip_config(bytes(size))
        body=ipv4();body[0]=2
        with self.assertRaises(ValueError):ril.s9_ip_config(body)

    def test_invalid_addresses_netmask_and_mtu_fail_closed(self):
        for address in ('0.0.0.0','127.0.0.1','224.0.0.1','169.254.1.1','255.255.255.255'):
            body=ipv4();body[3:7]=ipaddress.IPv4Address(address).packed
            with self.assertRaises(ValueError):ril.s9_ip_config(body)
        body=ipv4();body[19:23]=bytes((255,0,255,0))
        with self.assertRaisesRegex(ValueError,'Noncontiguous'):ril.s9_ip_config(body)
        for mtu in (0,575,65536,0xffffffff):
            body=ipv4();struct.pack_into('<I',body,152,mtu)
            with self.assertRaisesRegex(ValueError,'MTU'):ril.s9_ip_config(body)
        body=ipv4(flags=1|64|8192);body[35:51]=ipaddress.IPv6Address('2001:db8::5').packed
        struct.pack_into('<I',body,152,1279)
        with self.assertRaisesRegex(ValueError,'MTU'):ril.s9_ip_config(body)
        with self.assertRaises(ValueError):ril.s9_ip_config(ipv4(flags=0))

    def test_status_raw_reason_and_throttle_are_not_guessed(self):
        value=ril.s9_pdp_status(status(cause=149,throttle=0x01020304))
        self.assertTrue(value['active']);self.assertEqual(value['raw_end_reason'],149)
        self.assertEqual(value['throttle_timer_raw'],0x01020304)
        self.assertFalse(ril.s9_pdp_status(status(state=3))['active'])
        self.assertFalse(ril.s9_pdp_status(status(state=10))['active'])
        for body in (bytes(4),bytes(8),bytes(10),bytes((1,1,0,2,0))+bytes(4)):
            with self.assertRaises(ValueError):ril.s9_pdp_status(body)

    def test_private_status_record_has_only_raw_selected_fields(self):
        record=ril.private_s9_status_record(status(state=10,cause=149,throttle=0x01020304))
        self.assertEqual(record['pdp_status'],{'cid':1,'raw_state':10,'raw_end_reason':149,
            'aux_flag':True,'additional_status':0,'throttle_timer_raw':0x01020304})
        self.assertTrue(record['status_values_are_raw'])
        self.assertTrue(record['private_journal_only'])
        self.assertNotIn('raw_hex',str(record));self.assertNotIn('cause_name',str(record))
        with self.assertRaises(ValueError):ril.private_s9_status_record(bytes(4))

    def plan_at_activation(self, *, hold=False):
        p=ril.S9PDPPlan('fixture.apn',1,0,timeout=30,hold_qualified=hold)
        self.assertIsNone(p.registered(False,1))
        self.assertEqual(p.registered(True,2)[0],0x0d01)
        self.assertIsNone(p.registered(True,3))
        self.assertIsNone(p.ack(ack(0x0d04),3))
        self.assertIsNone(p.ack(ack(0x0d01,kind=2),3))
        command=p.ack(ack(0x0d01),4)
        self.assertEqual(command,(0x0d04,ril.s9_activate_pdp()))
        self.assertIsNone(p.ack(ack(0x0d01),5))
        return p

    def test_one_activation_requires_ack_status_and_ip_not_internet(self):
        p=self.plan_at_activation()
        p.event(0x0d09,ipv4(),6);p.event(0x0d10,status(),7)
        self.assertEqual(p.state,'activate-pending')
        p.ack(ack(0x0d04),8)
        self.assertEqual(p.state,'candidate-ip')
        self.assertIsNone(p.registered(True,9))
        self.assertIsNone(p.ack(ack(0x0d01),10))
        self.assertNotIn('internet',p.state)
        self.assertEqual(p.tick(30),'failed')
        self.assertEqual(p.reason,'deadline')
        self.assertEqual(p.cleanup(),(0x0d04,ril.s9_activate_pdp(enable=False)))
        self.assertIsNone(p.cleanup())

    def test_hold_applies_only_after_qualification_and_requires_fresh_link(self):
        early = self.plan_at_activation(hold=True)
        early.ack(ack(0x0d04), 8)
        self.assertEqual(early.tick(30), 'failed')
        for link in ({'registration_at': 20}, {'registered': False},
                     {'sim_ready': False}, {'at_ready': False}):
            p = self.plan_at_activation(hold=True)
            p.ack(ack(0x0d04), 8)
            p.event(0x0d09, ipv4(), 9)
            p.event(0x0d10, status(), 9)
            fresh = dict(registered=True, registration_at=39, sim_ready=True, at_ready=True)
            self.assertEqual(p.observe_link(40, **fresh), 'candidate-ip')
            self.assertEqual(p.observe_link(41, **(fresh | link)), 'failed')
            self.assertEqual(p.cleanup(), (0x0d04, ril.s9_activate_pdp(enable=False)))
            self.assertIsNone(p.cleanup())

    def test_held_ip_change_invalidates_route_configuration(self):
        p = self.plan_at_activation(hold=True)
        p.ack(ack(0x0d04), 8)
        p.event(0x0d09, ipv4(), 9)
        p.event(0x0d10, status(), 9)
        p.event(0x0d09, ipv4(), 39)
        self.assertEqual(p.state, 'candidate-ip')
        changed = ipv4()
        changed[6] = 3
        p.event(0x0d09, changed, 40)
        self.assertEqual(p.reason, 'ipv4-configuration-changed')
        self.assertEqual(p.state, 'failed')

    def test_candidate_private_record_once_and_only_selected_fields(self):
        p=self.plan_at_activation()
        self.assertIsNone(p.candidate_report())
        p.ack(ack(0x0d04),6)
        p.event(0x0d09,ipv4(),7)
        self.assertIsNone(p.candidate_report())
        p.event(0x0d10,status(),8)
        report=p.candidate_report()
        self.assertEqual(report['pdp_candidate'],{'cid':1,'ipv4':'100.64.1.2',
            'dns4':['1.1.1.1','8.8.8.8'],'gateway':'100.64.1.1','prefix4':24,'mtu':1500})
        self.assertFalse(report['internet_verified'])
        self.assertTrue(report['private_journal_only'])
        self.assertNotIn('raw_hex',str(report));self.assertNotIn('fixture.apn',str(report))
        self.assertIsNone(p.candidate_report())
        p.tick(30);self.assertIsNone(p.candidate_report())

    def test_negative_ack_malformed_events_and_disabled_are_terminal(self):
        p=ril.S9PDPPlan('fixture.apn',1,0)
        p.registered(True,1);self.assertIsNone(p.ack(ack(0x0d01,0x8001),2))
        self.assertEqual(p.state,'failed');self.assertIsNone(p.cleanup())
        for body in (bytes((1,))+bytes(3),status(state=0),status(state=10),status(state=11)):
            p=self.plan_at_activation();p.event(0x0d10,body,6)
            self.assertEqual(p.state,'failed')
        p=self.plan_at_activation();p.event(0x0d09,bytes(200),6)
        # CID0 belongs to another context and cannot satisfy this context.
        self.assertEqual(p.state,'activate-pending')
        p.event(0x0d09,bytes((1,))+bytes(199),7)
        self.assertEqual(p.state,'failed')
        self.assertIsNone(p.ack(ack(0x0d04),8))

    def test_reset_never_sends_cleanup_to_new_cp(self):
        p=self.plan_at_activation();p.cp_reset()
        self.assertEqual(p.reason,'cp-reset')
        self.assertIsNone(p.cleanup());self.assertIsNone(p.registered(True,8))

    def test_registration_must_be_complete_valid_status(self):
        for code in (1,5):
            self.assertTrue(ril.cereg_registration(('\r\n+CEREG: 0, %d\r\n'%code).encode()))
        for code in (0,2,3,4,6,7,8,9,10,11,15):
            self.assertFalse(ril.cereg_registration(('\r\n+CEREG: 0,%d\r\n'%code).encode()))
        self.assertIsNone(ril.cereg_registration(b'+CEREG: 0,1'))
        self.assertIsNone(ril.cereg_registration(b'+CEREG: 0,100\r\n'))
        self.assertIsNone(ril.cereg_registration(b'+CEREG: 10,1\r\n'))
        self.assertFalse(ril.cereg_registration(b'+CEREG: 0,1\r\n+CEREG: 0,3\r\n'))

    def test_time_bound_and_explicit_live_gate(self):
        for now in (float('nan'),float('inf'),-1,True):
            with self.assertRaises(ValueError):ril.S9PDPPlan('fixture.apn',1,now)
        for timeout in (0,61,True,1.5):
            with self.assertRaises(ValueError):ril.S9PDPPlan('fixture.apn',1,0,timeout)
        args=SimpleNamespace(activate_pdp_s9=False,confirm_reviewed_s9_pdp_layout=False,
                             configure_radio=True,pdp_cid=1,apn='fixture.apn')
        self.assertFalse(ril.validate_s9_opt_in(args))
        args.activate_pdp_s9=True
        with self.assertRaises(ValueError):ril.validate_s9_opt_in(args)
        args.confirm_reviewed_s9_pdp_layout=True
        self.assertTrue(ril.validate_s9_opt_in(args))
        args.pdp_cid=2
        with self.assertRaises(ValueError):ril.validate_s9_opt_in(args)


if __name__=='__main__':unittest.main()

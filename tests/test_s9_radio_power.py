# SPDX-License-Identifier: GPL-2.0-only
import ast
import importlib.util
from pathlib import Path
import struct
import unittest

FILE=Path(__file__).resolve().parents[1]/'experiments/modem/ril-lab.py'
spec=importlib.util.spec_from_file_location('s9_radio',FILE)
ril=importlib.util.module_from_spec(spec);spec.loader.exec_module(ril)


class RadioWireFacts(unittest.TestCase):
    def test_phonebook_completion_preserves_only_existing_sim_readiness(self):
        ready = False
        for status in (0, 130, 0, 130, 131):
            ready = ril.sim_ready_after_status(ready, status)
            self.assertTrue(ready)
        self.assertFalse(ril.sim_ready_after_status(False, 131))
        for status in (1, 3, 5, 128, 129, 255):
            self.assertFalse(ril.sim_ready_after_status(True, status))
            self.assertFalse(ril.sim_ready_after_status(False, status))

    def test_own_stock_radio_normal_exec_frame(self):
        command,body,kind=ril.s9_radio_normal()
        frame=struct.pack('<HBBBBB',len(body)+7,1,255,command>>8,command&255,kind)+body
        self.assertEqual(frame,bytes.fromhex('090001ff0107010202'))

    def test_no_automatic_at_radio_toggle(self):
        strings=[n.value for n in ast.walk(ast.parse(FILE.read_text())) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
        self.assertNotIn('AT+CFUN=4',strings)
        self.assertNotIn('AT+CFUN=1',strings)
        self.assertIn('AT+CFUN?',strings)

    def test_ps_attach_is_not_pdp_activation_or_detach(self):
        command,body,kind=ril.s9_ps_attach()
        frame=struct.pack('<HBBBBB',len(body)+7,1,255,command>>8,command&255,kind)+body
        self.assertEqual(frame,bytes.fromhex('0a0001ff0d0303010000'))

    def test_automatic_selection_carries_no_manual_operator(self):
        command,body,kind=ril.s9_select_automatic()
        frame=struct.pack('<HBBBBB',len(body)+7,1,255,command>>8,command&255,kind)+body
        self.assertEqual(frame,bytes.fromhex('0f0001ff08020302000000000000ff'))

    def test_attach_profile_uses_reviewed_ipv4_mapping_consistent_with_pdp(self):
        body=ril.s9_lte_attach_profile('fixture.example')
        self.assertEqual(len(body),194)
        self.assertEqual(body[:3],bytes((1,1,2)))
        self.assertEqual(body[3:104],b'fixture.example'.ljust(101,b'\0'))
        self.assertEqual(body[104:192],bytes(88))
        self.assertEqual(body[192:],bytes((2,0)))
        # Independently reviewed string -> internal enum -> wire mapping:
        # IP ->1 ->2; IPV6 ->2 ->5; IPV4V6 ->3 ->6. Keep home/roam and
        # context definition consistent instead of assuming enum2 means IPv4.
        self.assertEqual(body[2],ril.s9_define_pdp('fixture.example')[2])
        self.assertEqual(ril.s9_define_pdp('fixture.example')[2],2)
        for apn in ['', 'bad/apn', 'x'*101, 'x'*125]:
            with self.assertRaises(ValueError):ril.s9_lte_attach_profile(apn)
        with self.assertRaises(ValueError):ril.s9_define_pdp('x'*101)

    def test_home_network_discards_subscriber_suffix_and_redacts_all_fragments(self):
        # Synthetic fixtures only; no real SIM identity.
        for suffix in ['1234567890','9999999999']:
            response=('AT+CIMI\r\r\n45008'+suffix+'\r\nOK\r\n').encode()
            result=ril.home_network_only(response)
            self.assertEqual(result,{'mcc':'450','mnc':'08','subscriber_identity_redacted':True})
            self.assertNotIn(suffix,str(result))
            for start in range(len(response)):
                record=ril.at_log_record(response[start:start+3],'AT+CIMI')
                self.assertTrue(record['at_status_redacted'])
                self.assertNotIn('at_status',record)
        self.assertIsNone(ril.home_network_only(b'AT+CIMI\r\nERROR\r\n'))
        self.assertEqual(ril.home_network_only(b'\r\n310260123456789\r\n')['mnc'],None)

    def test_device_identity_reports_only_validity_and_never_value(self):
        # Publicly documented synthetic Luhn example, not this handset.
        response=b'AT+CGSN\r\n490154203237518\r\nOK\r\n'
        result=ril.device_identity_status_only(response)
        self.assertEqual(result,{'imei_format_valid':True,'default_identity':False,'device_identity_redacted':True})
        self.assertNotIn('490154203237518',str(result))
        for field in (b'IMEI: 490154203237518', b'IMEI = 490154203237518',
                      b'+CGSN: "490154203237518"'):
            self.assertEqual(ril.device_identity_status_only(b'AT+CGSN\r\n'+field+b'\r\nOK\r\n'),result)
        self.assertIsNone(ril.device_identity_status_only(b'\r\n149015420323751899\r\n'))
        self.assertIsNone(ril.device_identity_status_only(b'\r\n490154203237518 490154203237518\r\n'))
        self.assertIsNone(ril.device_identity_status_only(b'\r\n490154203237518\r\nERROR\r\n'))
        self.assertTrue(ril.at_log_record(response,'AT+CGSN')['at_status_redacted'])
        self.assertFalse(ril.device_identity_status_only(b'\r\n490154203237519\r\n')['imei_format_valid'])
        self.assertTrue(ril.device_identity_status_only(b'\r\n000000000000000\r\n')['default_identity'])
        self.assertIsNone(ril.device_identity_status_only(b'ERROR'))

    def test_unknown_identity_reply_shape_never_contains_identity(self):
        shape = ril.device_identity_reply_shape(b'AT+CGSN\r\n+CGSN: "490154203237518"\r\nOK\r\n')
        self.assertEqual(shape, {'terminal_error': False, 'cgsn_prefix': True,
                                'quoted_numeric_field': True, 'numeric_field_lengths': [15]})
        self.assertNotIn('490154203237518', str(shape))
        for reply in (b'ERROR\r\n', b'\r\n+CME ERROR: 4\r\n'):
            self.assertTrue(ril.device_identity_reply_shape(reply)['terminal_error'])
        self.assertFalse(ril.device_identity_reply_shape(b'\r\nNO ERROR IN VALUE\r\n')['terminal_error'])
        self.assertEqual(len(ril.device_identity_reply_shape((b'123456789012345 ' * 100))['numeric_field_lengths']), 8)

    def test_network_scan_counts_do_not_expose_operator_details(self):
        reply = b'AT+COPS=?\r\n+COPS: (1,"Test Carrier A","A","45008",7),(3,"Test Carrier B","B","45005",2),(2,"Test Carrier A","A","45008",7),,(0-4),(0-2)\r\nOK\r\n'
        result = ril.network_scan_status_only(reply)
        self.assertEqual(result, {'operator_count':3, 'available_count':1,
                                 'current_count':1, 'forbidden_count':1,
                                 'access_technology_counts':{'7':2, '2':1}, 'terminal_error':False})
        for private in ('45008', '45005', 'Test Carrier'):
            self.assertNotIn(private,str(result))
        for start in range(len(reply)):
            self.assertNotIn('at_status',ril.at_log_record(reply[start:start+7],'AT+COPS=?'))
        self.assertEqual(ril.network_scan_status_only(b'\r\nERROR\r\n')['operator_count'],0)
        self.assertTrue(ril.network_scan_status_only(b'\r\nERROR\r\n')['terminal_error'])
        self.assertEqual(ril.network_scan_status_only(b'(1,"A","A","4500800",7)')['operator_count'],0)

    def test_s9_network_scan_stock_requests_and_bounded_private_decode(self):
        for cancel, expected in ((False,'070001ff080402'),(True,'070001ff080403')):
            command,body,kind=ril.s9_network_scan_request(cancel=cancel)
            frame=struct.pack('<HBBBBB',7+len(body),1,255,command>>8,command&255,kind)+body
            self.assertEqual(frame,bytes.fromhex(expected))
        entry=bytes((2,))+b'45008#'+bytes((33,0,0))
        result=ril.s9_network_scan_status_only(b'\x01'+entry)
        self.assertEqual(result,{'operator_count':1,'status_code_counts':{'2':1},
                                 'access_technology_code_counts':{'33':1}})
        self.assertNotIn('45008',str(result))
        self.assertEqual(ril.s9_network_scan_status_only(b'\0')['operator_count'],0)
        for body in (b'',b'\x01',b'\0'+entry,b'\x02'+entry,b'\x01'+entry[:-1],b'\x01'+entry+b'\0'):
            with self.assertRaises(ValueError):ril.s9_network_scan_status_only(body)

    def test_registration_cause_excludes_location_bytes(self):
        body=bytes((33,3,4))+b'PRIVATE'+bytes((15,))+b'UNEXPOSED'
        self.assertEqual(ril.s9_registration_status_only(body),{
            'access_technology_code':33,'domain_code':3,'registration_code':4,
            'registration_failure_cause_code':15})
        self.assertNotIn('PRIVATE',str(ril.s9_registration_status_only(body)))
        for size in range(11):
            with self.assertRaises(ValueError):ril.s9_registration_status_only(body[:size])


if __name__=='__main__':unittest.main()

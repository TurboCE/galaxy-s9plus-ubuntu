# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('ril',Path(__file__).parents[1]/'experiments/modem/ril-lab.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class CeregDiagnosticsTests(unittest.TestCase):
    def test_query_redacts_location_and_retains_numeric_reason_domain(self):
        body=b'AT+CEREG?\r\r\n+CEREG: 3,3,"AA12","DEADBEEF",7,0,6\r\nOK\r\n'
        result=m.cereg_query_status_only(body)
        self.assertEqual(result,{'reporting_mode':3,'registration_code':3,'location_fields_redacted':True,
                                 'access_technology_code':7,'cause_type_code':0,'reject_cause_code':6})
        self.assertNotIn('AA12',json.dumps(result));self.assertNotIn('DEADBEEF',json.dumps(result))
        self.assertFalse(m.completed_cereg_registration(body,'AT+CEREG?'))

    def test_complete_acknowledged_query_required_for_initial_pdp(self):
        good=b'AT+CEREG?\r\r\n+CEREG: 0,1\r\nOK\r\n'
        self.assertTrue(m.completed_cereg_registration(good,'AT+CEREG?'))
        for command in [None,'AT+CSQ','AT+CEREG=?']:
            self.assertIsNone(m.completed_cereg_registration(good,command))
        for body in [good.replace(b'OK\r\n',b''),good.replace(b'OK',b'ERROR'),
                     good.replace(b'AT+CEREG?\r',b''),b'AT+CEREG?\r\n+CEREG: 0,1']:
            self.assertIsNone(m.completed_cereg_registration(body,'AT+CEREG?'))
        denied=good.replace(b'+CEREG: 0,1\r\n',b'+CEREG: 0,1\r\n+CEREG: 0,3\r\n')
        self.assertEqual(m.cereg_query_status_only(denied)['registration_code'],3)
        self.assertFalse(m.completed_cereg_registration(denied,'AT+CEREG?'))

    def test_reporting_capabilities_ranges_lists_and_malformed(self):
        for body,expected in [(b'+CEREG: (0-5)\r\n',list(range(6))),
                              (b'+CEREG: (0, 1,2,3)\r\n',[0,1,2,3]),
                              (b'+CEREG: (0-2,4)\n',[0,1,2,4])]:
            self.assertEqual(m.cereg_supported_modes(body),expected)
        for body in [b'+CEREG: (5-0)\n',b'+CEREG: (0-9)\n',b'+CEREG: (0-5)',b'ERROR\r\n']:
            self.assertIsNone(m.cereg_supported_modes(body))

    def test_malformed_status_is_not_registration_evidence(self):
        for body in [b'+CEREG: 0,100\n',b'+CEREG: 9,1\n',b'+CEREG: 3,"AA12",7\n',
                     b'+CEREG: 3,3,"unfinished\n',b'+CEREG: 3,3,,,7,9,6\n',
                     b'+CEREG: 3,3,,,7,0,999\n']:
            self.assertIsNone(m.cereg_query_status_only(body))
        for command in ['AT+CEREG?','AT+CEREG=?']:
            self.assertNotIn('AA12',json.dumps(m.at_log_record(b'private-AA12',command)))


if __name__=='__main__':unittest.main()

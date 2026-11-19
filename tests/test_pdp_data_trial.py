# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import ipaddress
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('data_trial',ROOT/'scripts/g965n/test-pdp-data.py')
trial=importlib.util.module_from_spec(spec);spec.loader.exec_module(trial)


def packet(ident=7,flags=0x8180):
    question=b'\x04test\x07invalid\0'+struct.pack('!HH',1,1)
    return struct.pack('!HHHHHH',ident,flags,1,1,0,0)+question+b'\xc0\x0c'+struct.pack('!HHIH',1,1,30,4)+bytes((203,0,113,8))


class DataTrialTests(unittest.TestCase):
    def test_policy_collision_refuses_before_changing_interface_or_routes(self):
        config = {'ipv4': '192.0.2.3', 'dns4': ['192.0.2.53'], 'mtu': 1450}
        for rules, routes in (
            ('[{"priority":19650,"table":"100"}]', '[]'),
            ('[{"priority":19649,"table":"9650"}]', '[]'),
            ('[]', '[{"table":"9650","dev":"existing"}]'),
        ):
            responses = ['[{"flags":[],"link_type":"ppp"}]', '[{"addr_info":[]}]',
                         '[]', rules, routes]
            with patch.object(trial.subprocess, 'check_output', side_effect=responses), \
                    patch.object(trial.subprocess, 'run') as mutate:
                with self.assertRaisesRegex(ValueError, 'in use'):
                    trial.network_trial(config, policy_route=True)
                mutate.assert_not_called()

    def test_real_dns_answer_matching_id_and_compressed_name(self):
        self.assertEqual(trial.dns_address(packet(),7,'test.invalid'),'203.0.113.8')
        for value in (packet(8),packet(flags=0x8183),packet(flags=0x8380),packet()[:8],packet()[:-2]):
            with self.assertRaises((ValueError,struct.error)):
                trial.dns_address(value,7,'test.invalid')

    def test_aaaa_follows_cname_without_accepting_unrelated_addresses(self):
        question = b'\x04test\x07invalid\0' + struct.pack('!HH', 28, 1)
        query_name = b'\xc0\x0c'
        alias_name = b'\x04edge\xc0\x11'
        address = ipaddress.IPv6Address('2001:db8::8').packed
        aaaa = struct.pack('!HHIH', 28, 1, 30, len(address)) + address
        cname = query_name + struct.pack('!HHIH', 5, 1, 30, len(alias_name)) + alias_name
        header = struct.pack('!HHHHHH', 7, 0x8180, 1, 2, 0, 0)
        response = header + question + alias_name + aaaa + cname
        self.assertEqual(trial.dns_address(response, 7, 'Test.Invalid.', 28), '2001:db8::8')
        for malformed in (
            header + question + alias_name + aaaa + alias_name + aaaa,
            header + question + alias_name + aaaa + query_name +
            struct.pack('!HHIH', 5, 1, 30, len(query_name)) + query_name,
        ):
            with self.assertRaises(ValueError):
                trial.dns_address(malformed, 7, 'test.invalid', 28)
        with self.assertRaisesRegex(ValueError, 'Unexpected DNS question'):
            trial.dns_address(response, 7, 'other.invalid', 28)
        with self.assertRaisesRegex(ValueError, 'Unexpected DNS question'):
            trial.dns_address(response, 7, 'test.invalid', 1)

    def test_only_live_candidate_and_bounded_modem_configuration(self):
        config={'cid':1,'ipv4':'10.0.0.2','dns4':['192.0.2.53'],'gateway':None,'prefix4':None,'mtu':1450}
        events=[{'pdp_state':'candidate-ip'},{'pdp_candidate':config}]
        self.assertEqual(trial.candidate_from(events),config)
        for tail in ([{'pdp_state':'failed'}],[{'pdp_cleanup':'requested'}],[{'pdp_state':'await-ip-and-status'}]):
            with self.assertRaises(ValueError):trial.candidate_from(events+tail)
        for patch in ({'cid':True},{'cid':2},{'ipv4':'127.0.0.1'},{'ipv4':'::1'},
                {'dns4':[]},{'dns4':['0.0.0.0']},{'dns4':['192.0.2.1']*3},{'mtu':0},{'mtu':True}):
            with self.assertRaises(ValueError):trial.candidate_from([{'pdp_state':'candidate-ip'},{'pdp_candidate':{**config,**patch}}])

    def test_reconnect_requires_a_new_live_candidate_in_the_expected_generation(self):
        config = {'cid': 1, 'ipv4': '192.0.2.3', 'dns4': ['192.0.2.53'], 'mtu': 1450}
        online = [{'pdp_state': 'candidate-ip'}, {'pdp_candidate': config}]
        first = [{'pdp_generation': 1}, *online]
        released = [*first, {'pdp_cleanup': 'cycle-release-requested'}]
        next_plan = [*released, {'pdp_generation': 2}]
        self.assertEqual(trial.candidate_from(first, 1), config)
        self.assertEqual(trial.candidate_from(next_plan + online, 2), config)
        for events, expected in ((first, 2), (released, 1), (next_plan, 2),
                                 (next_plan + online, 1), (first + [{'pdp_generation': 2}] + online, 2)):
            with self.assertRaises(ValueError):
                trial.candidate_from(events, expected)


if __name__=='__main__':unittest.main()

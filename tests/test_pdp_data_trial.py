# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
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
        self.assertEqual(trial.dns_a(packet(),7),'203.0.113.8')
        for value in (packet(8),packet(flags=0x8183),packet(flags=0x8380),packet()[:8],packet()[:-2]):
            with self.assertRaises((ValueError,IndexError,struct.error)):trial.dns_a(value,7)

    def test_only_live_candidate_and_bounded_modem_configuration(self):
        config={'cid':1,'ipv4':'10.0.0.2','dns4':['192.0.2.53'],'gateway':None,'prefix4':None,'mtu':1450}
        events=[{'pdp_state':'candidate-ip'},{'pdp_candidate':config}]
        self.assertEqual(trial.candidate_from(events),config)
        for tail in ([{'pdp_state':'failed'}],[{'pdp_cleanup':'requested'}],[{'pdp_state':'await-ip-and-status'}]):
            with self.assertRaises(ValueError):trial.candidate_from(events+tail)
        for patch in ({'cid':True},{'cid':2},{'ipv4':'127.0.0.1'},{'ipv4':'::1'},
                {'dns4':[]},{'dns4':['0.0.0.0']},{'dns4':['192.0.2.1']*3},{'mtu':0},{'mtu':True}):
            with self.assertRaises(ValueError):trial.candidate_from([{'pdp_state':'candidate-ip'},{'pdp_candidate':{**config,**patch}}])


if __name__=='__main__':unittest.main()

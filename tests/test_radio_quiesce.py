# SPDX-License-Identifier: GPL-2.0-only
"""RF low-power confirmation, channel lifetime and no-reset boundaries."""
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
import socket
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('quiesce_ril',ROOT/'experiments/modem/ril-lab.py')
ril=importlib.util.module_from_spec(spec);spec.loader.exec_module(ril)
spec=importlib.util.spec_from_file_location('quiesce_launcher',ROOT/'scripts/g965n/run-ril-test.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)


def ipc(command, body=b'',kind=3):
    return struct.pack('<HBBBBB',7+len(body),1,255,command>>8,command&255,kind)+body


class QuiesceTests(unittest.TestCase):
    def test_only_matching_state_confirms_not_ack_or_late_or_wrong_kind(self):
        self.assertEqual(ril.s9_radio_low_power(),(0x0107,b'\x01\x00',1))
        p=ril.RadioLowPowerDrain(10)
        p.event(ipc(0x8001,struct.pack('<BBBH',1,7,1,0x8000)),11)
        self.assertFalse(p.result()['radio_lpm_confirmed'])
        p.event(ipc(0x0107,b'\x01',1),12)
        self.assertIsNone(p.confirmed_at)
        p.event(ipc(0x0107,b'\x02'),13)
        self.assertIsNone(p.confirmed_at)
        p.event(ipc(0x0107,b'\x01'),14)
        self.assertTrue(p.pending(15.99));self.assertFalse(p.pending(16))
        self.assertTrue(p.result()['radio_lpm_confirmed'])
        self.assertTrue(p.result(16)['radio_tail_drain_complete'])
        self.assertFalse(p.result()['cp_power_off_verified'])
        late=ril.RadioLowPowerDrain(0);late.event(ipc(0x0107,b'\x01'),10)
        self.assertFalse(late.result()['radio_lpm_confirmed'])

    def test_restart_rejection_and_leave_lpm_fail_without_retry(self):
        for message,reason in ((ipc(0x0101), 'cp-restarted'),
                (ipc(0x8001,struct.pack('<BBBH',1,7,1,0x8001)),'lpm-rejected'),
                (ipc(0x0107,b'\x02'),'left-lpm')):
            p=ril.RadioLowPowerDrain(0);p.event(ipc(0x0107,b'\x01'),1);p.event(message,2)
            self.assertFalse(p.pending(2));self.assertFalse(p.result()['radio_lpm_confirmed'])
            self.assertEqual(p.result()['radio_drain_failure'],reason)
        for seconds in (0,-1,11):
            with self.assertRaises(ValueError):ril.RadioLowPowerDrain(0,seconds)

    def sockets(self):
        pairs=[socket.socketpair() for _ in range(3)]
        for pair in pairs:
            for s in pair:self.addCleanup(s.close)
        return pairs

    def test_transport_serves_rfs_until_low_power_reply_and_keeps_fds_open(self):
        pairs=self.sockets();fds=[p[0].fileno() for p in pairs]
        requests=[];seen=[]
        # A queued stale LPM notification must be consumed before the request.
        pairs[0][1].sendall(ipc(0x0107,b'\x01'))
        def send(*request):
            requests.append(request)
            pairs[0][1].sendall(ipc(0x0107,b'\x01'))
            pairs[1][1].sendall(struct.pack('<IBBi',10,6,1,1))
        def handle(message):
            seen.append(message);return struct.pack('<IBBii',14,6,1,0,0)
        with redirect_stdout(io.StringIO()):
            result=ril.drain_radio_low_power(send,fds,{fd:bytearray() for fd in fds[:2]},
                    SimpleNamespace(handle=handle),None,seconds=0.05)
        self.assertEqual(requests,[ril.s9_radio_low_power()]);self.assertTrue(result['radio_lpm_confirmed'])
        self.assertEqual(len(seen),1);self.assertEqual(pairs[1][1].recv(14),struct.pack('<IBBii',14,6,1,0,0))
        for fd in fds:__import__('os').fstat(fd)

    def test_stale_reply_alone_does_not_confirm_and_partial_old_frame_refuses_send(self):
        pairs=self.sockets();fds=[p[0].fileno() for p in pairs]
        pairs[0][1].sendall(ipc(0x0107,b'\x01'))
        requests=[]
        with redirect_stdout(io.StringIO()):
            result=ril.drain_radio_low_power(lambda *r:requests.append(r),fds,
                {fd:bytearray() for fd in fds[:2]},None,None,seconds=0.02)
        self.assertFalse(result['radio_lpm_confirmed']);self.assertEqual(len(requests),1)
        with self.assertRaisesRegex(RuntimeError,'incomplete'):
            ril.drain_radio_low_power(lambda *r:self.fail('must not send'),fds,
                {fds[0]:bytearray(b'\x08\x00'),fds[1]:bytearray()},None,None,seconds=0.02)

    def test_existing_online_and_observe_only_rejected_before_io(self):
        for online,observe in ((True,False),(False,True),(True,True)):
            args=SimpleNamespace(quiesce_radio_on_exit=True,attach_online=online,observe_only=observe)
            with patch.object(launcher.argparse.ArgumentParser,'parse_args',return_value=args), \
                    patch.object(launcher,'load_runtime') as load, \
                    patch.object(launcher.subprocess,'run') as run, \
                    patch('sys.stderr',io.StringIO()):
                with self.assertRaises(SystemExit):launcher.main()
                load.assert_not_called();run.assert_not_called()


if __name__=='__main__':unittest.main()

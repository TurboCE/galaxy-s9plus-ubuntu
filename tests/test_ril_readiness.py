# SPDX-License-Identifier: GPL-2.0-only
"""Service readiness is the child's open-channel state, not the start job."""
import importlib.util
import io
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace,ModuleType
import unittest
from unittest.mock import patch
from contextlib import nullcontext

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
launcher=load('ready_launcher','scripts/g965n/run-ril-test.py')
ril=load('ready_child','experiments/modem/ril-lab.py')


def state(active='activating',sub='start',pid='321',kind='notify',result='success'):
    return f'Type={kind}\nActiveState={active}\nSubState={sub}\nMainPID={pid}\nResult={result}\n'


class ReadinessTests(unittest.TestCase):
    def test_waits_for_notify_running_main_not_just_queued_job(self):
        with patch.object(launcher.subprocess,'check_output',side_effect=[state(),state('active','running')]) as read, \
                patch.object(launcher.time,'sleep'):
            launcher.wait_for_lab_ready()
        self.assertEqual(read.call_count,2)

    def test_failed_inactive_wrong_type_or_missing_main_never_ready(self):
        for output in (state('failed','failed'),state('inactive','dead'),state('deactivating','stop'),
                state('active','running',kind='simple'),state('active','running',pid='0'),
                state('active','exited'),state('active','running',result='exit-code'),
                state('active','running',pid='bad'),'',state('active','running').replace('Result=success','')):
            with self.subTest(output=output),patch.object(launcher.subprocess,'check_output',return_value=output):
                with self.assertRaises(RuntimeError):launcher.wait_for_lab_ready()

    def test_startup_timeout_is_bounded(self):
        with patch.object(launcher.subprocess,'check_output',return_value=state()):
            with self.assertRaises(TimeoutError):launcher.wait_for_lab_ready(0.01)
        for seconds in (0,-1,11):
            with self.assertRaises(ValueError):launcher.wait_for_lab_ready(seconds)

    def test_main_notification_uses_real_local_datagram(self):
        with tempfile.TemporaryDirectory() as name:
            path=str(Path(name)/'notify.sock')
            with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as receiver:
                receiver.bind(path);receiver.settimeout(1)
                with patch.dict(os.environ,{'NOTIFY_SOCKET':path}):ril.notify_channels_ready()
                self.assertEqual(receiver.recv(256),b'READY=1\nSTATUS=Private IPC/RFS channels ready')
        for address in ('','not-a-socket'):
            with patch.dict(os.environ,{'NOTIFY_SOCKET':address}):
                with self.assertRaises(RuntimeError):ril.notify_channels_ready()

    def test_readiness_failure_stops_child_without_vendor_launch(self):
        args=SimpleNamespace(apn='fixture.apn',lab_directory=ROOT/'experiments/modem',
            runtime_helper=ROOT/'scripts/g965n/vendor-runtime.py',seconds=30,activate_pdp_s9=False,
            confirm_reviewed_s9_pdp_layout=False)
        runtime=SimpleNamespace(shared_runtime_lock=lambda:nullcontext(),launch_receipt_digest=lambda:'a'*64)
        repo=ModuleType('gi.repository');repo.GLib=SimpleNamespace(Variant=lambda sig,value:value)
        bus=SimpleNamespace(call_sync=lambda *a:None)
        repo.Gio=SimpleNamespace(BusType=SimpleNamespace(SYSTEM=0),DBusProxy=SimpleNamespace(new_for_bus_sync=lambda *a:bus))
        gi=ModuleType('gi');gi.repository=repo
        commands=[]
        def run(command,**kwargs):
            commands.append(command);return SimpleNamespace(returncode=3)
        with patch.object(launcher.argparse.ArgumentParser,'parse_args',return_value=args), \
                patch.object(launcher.os,'geteuid',return_value=0), \
                patch.object(Path,'read_bytes',return_value=b'samsung,star2lte\0'), \
                patch.object(launcher.subprocess,'run',side_effect=run), \
                patch.object(launcher,'load_runtime',return_value=runtime), \
                patch.object(launcher,'verify_private_runtime'), \
                patch.object(launcher,'wait_for_lab_ready',side_effect=TimeoutError('fixture timeout')), \
                patch.dict(sys.modules,{'gi':gi,'gi.repository':repo}):
            with self.assertRaises(TimeoutError):launcher.main()
        self.assertTrue(all(command[0]=='systemctl' for command in commands))
        self.assertEqual(commands[-1],['systemctl','stop','g965n-ril-lab-test.service'])


if __name__=='__main__':unittest.main()

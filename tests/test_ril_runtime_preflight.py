# SPDX-License-Identifier: GPL-2.0-only
"""No unit/vendor launch before private provenance and runtime checks."""
import importlib.util
import io
import ast
import builtins
import sys
from pathlib import Path
from types import SimpleNamespace, ModuleType
import unittest
import tempfile
import stat
from contextlib import nullcontext, redirect_stdout
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ril_launcher_test', ROOT/'scripts/g965n/run-ril-test.py')
launcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(launcher)

spec = importlib.util.spec_from_file_location('cbd_launcher_test', ROOT/'scripts/g965n/run-cbd-test.py')
cbd = importlib.util.module_from_spec(spec); spec.loader.exec_module(cbd)


class StartupPreflightTests(unittest.TestCase):
    def test_network_scan_refuses_configuration_and_short_window_before_io(self):
        for observe, online, pdp, seconds in ((False,True,False,120), (True,False,False,120),
                                               (True,True,True,120), (True,True,False,109)):
            args=SimpleNamespace(scan_networks=True,observe_only=observe,attach_online=online,
                                 activate_pdp_s9=pdp,seconds=seconds)
            with patch.object(launcher.argparse.ArgumentParser,'parse_args',return_value=args), \
                    patch.object(launcher,'load_runtime') as load, \
                    patch.object(launcher.subprocess,'run') as run, \
                    patch.object(sys,'stderr',io.StringIO()):
                with self.assertRaises(SystemExit):launcher.main()
                load.assert_not_called();run.assert_not_called()

    def test_s9_network_scan_has_same_preflight_and_excludes_other_scan(self):
        for observe, online, pdp, seconds, at_scan in ((False,True,False,120,False),
                (True,False,False,120,False),(True,True,True,120,False),
                (True,True,False,109,False),(True,True,False,120,True)):
            args=SimpleNamespace(scan_networks=at_scan,scan_networks_s9=True,
                observe_only=observe,attach_online=online,activate_pdp_s9=pdp,seconds=seconds)
            with patch.object(launcher.argparse.ArgumentParser,'parse_args',return_value=args), \
                    patch.object(launcher,'load_runtime') as load, \
                    patch.object(launcher.subprocess,'run') as run, \
                    patch.object(sys,'stderr',io.StringIO()):
                with self.assertRaises(SystemExit):launcher.main()
                load.assert_not_called();run.assert_not_called()

    def runtime(self):
        return SimpleNamespace(ROOT=Path('/fixture/runtime'), STATE=Path('/fixture/state'),
            DATA=Path('/fixture/state/data'), assert_board=MagicMock(),
            read_provenance=MagicMock(return_value={'fixture': True}),
            validate_modem_state=MagicMock(), verify_private_bindings=MagicMock(),
            shared_runtime_lock=lambda: nullcontext(), safe_components=MagicMock(), regular_info=MagicMock())

    def test_cbd_lifetime_monitor_and_child_validation_command(self):
        runtime = SimpleNamespace(RUNTIME_LOCK=Path('/run/g965n-vendor-runtime.lock'),
            launch_receipt_digest=lambda: 'a'*64)
        for trace in (False, True):
            args = SimpleNamespace(trace=trace, runtime_helper=ROOT/'scripts/g965n/vendor-runtime.py', seconds=30)
            command = cbd.cbd_command(args, runtime)
            self.assertEqual(command[:4], ['/usr/bin/flock', '--shared', '--nonblock', str(runtime.RUNTIME_LOCK)])
            self.assertNotIn('--no-fork', command)  # monitor survives vendor FD closing
            self.assertIn('--child', command)
            self.assertEqual(command[command.index('--expected-receipt-sha256')+1], 'a'*64)
            self.assertNotIn('/vendor/bin/cbd', command)  # only child may exec it
            with patch.object(cbd, 'new_trace_path', return_value='/fixture/new-private.strace'):
                vendor = cbd.vendor_command(args)
            chroot = vendor.index('/usr/sbin/chroot')
            self.assertEqual(vendor[chroot+1], str(cbd.ROOT))
            self.assertEqual(vendor[chroot+2], '/vendor/bin/cbd')
            if trace:
                self.assertLess(vendor.index('/usr/bin/strace'), chroot)
            else:
                self.assertNotIn('/usr/bin/strace', vendor)

    def test_each_trace_preserves_earlier_evidence(self):
        with tempfile.TemporaryDirectory() as name:
            directory=Path(name);directory.chmod(0o700)
            with patch.object(cbd,'TRACE_DIR',directory):
                a=Path(cbd.new_trace_path());a.write_text('earlier evidence')
                b=Path(cbd.new_trace_path())
                self.assertNotEqual(a,b)
                self.assertEqual(a.read_text(),'earlier evidence')
                self.assertEqual(stat.S_IMODE(b.stat().st_mode),0o600)
                directory.chmod(0o755)
                with self.assertRaisesRegex(RuntimeError,'private'):cbd.new_trace_path()

    def test_online_attachment_refuses_all_other_states_and_closes_fd(self):
        for state in (0,1,2,3,4,5,6,7,8,9,-1):
            with patch.object(launcher.os,'open',return_value=19), \
                    patch.object(launcher.fcntl,'ioctl',return_value=state) as ioctl, \
                    patch.object(launcher.os,'close') as close:
                if state==4:launcher.require_online_cp()
                else:
                    with self.assertRaisesRegex(RuntimeError,'STATE_ONLINE'):launcher.require_online_cp()
                ioctl.assert_called_once_with(19,0x6f27,0)
                close.assert_called_once_with(19)

    def test_cbd_child_revalidates_before_vendor_exec(self):
        args = SimpleNamespace(child=True, trace=False, seconds=30,
            runtime_helper=ROOT/'scripts/g965n/vendor-runtime.py', expected_receipt_sha256='a'*64)
        runtime = self.runtime()
        runtime.validate_launch_state = MagicMock(side_effect=RuntimeError('stale queued state'))
        fake_spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module: None))
        with patch.object(cbd.argparse.ArgumentParser, 'parse_args', return_value=args), \
                patch.object(cbd.os, 'geteuid', return_value=0), \
                patch.object(cbd.os.path, 'ismount', return_value=True), \
                patch.object(Path, 'read_bytes', return_value=b'samsung,star2lte\0'), \
                patch.object(cbd.importlib.util, 'spec_from_file_location', return_value=fake_spec), \
                patch.object(cbd.importlib.util, 'module_from_spec', return_value=runtime), \
                patch.object(cbd.os, 'execv') as execv:
            with self.assertRaisesRegex(RuntimeError, 'stale queued state'): cbd.main()
            runtime.validate_launch_state.assert_called_once_with('a'*64)
            execv.assert_not_called()

    def test_incomplete_pdp_opt_in_is_rejected_before_any_cp_operation(self):
        for selected, reviewed in ((True, False), (False, True)):
            args=SimpleNamespace(activate_pdp_s9=selected,confirm_reviewed_s9_pdp_layout=reviewed,
                                 apn='fixture.apn')
            with patch.object(launcher.argparse.ArgumentParser,'parse_args',return_value=args), \
                    patch.object(launcher.subprocess,'run') as run, \
                    patch.object(launcher,'load_runtime') as load:
                with self.assertRaisesRegex(SystemExit,'explicit opt-in'):launcher.main()
                run.assert_not_called();load.assert_not_called()

    def test_provenance_rejection_happens_before_unit_or_vendor_launch(self):
        args = SimpleNamespace(apn='fixture.apn', lab_directory=ROOT/'experiments/modem',
            runtime_helper=ROOT/'scripts/g965n/vendor-runtime.py', seconds=30)
        with patch.object(launcher.argparse.ArgumentParser, 'parse_args', return_value=args), \
                patch.object(launcher.os, 'geteuid', return_value=0), \
                patch.object(Path, 'read_bytes', return_value=b'samsung,star2lte\0'), \
                patch.object(launcher.subprocess, 'run', return_value=SimpleNamespace(returncode=3)), \
                patch.object(launcher, 'load_runtime', return_value=self.runtime()), \
                patch.object(launcher, 'verify_private_runtime', side_effect=RuntimeError('bad provenance')), \
                patch.dict(sys.modules, {'gi': None}):
            with self.assertRaisesRegex(RuntimeError, 'bad provenance'): launcher.main()

    def test_parent_has_no_forced_off_and_validation_precedes_startup(self):
        args=SimpleNamespace(apn='fixture.apn',lab_directory=ROOT/'experiments/modem',
            runtime_helper=ROOT/'scripts/g965n/vendor-runtime.py',seconds=30,activate_pdp_s9=False,
            confirm_reviewed_s9_pdp_layout=False,pdp_cid=1,pdp_seconds=30,serve_private_rfs_diagnostics=True)
        runtime=self.runtime();runtime.launch_receipt_digest=lambda:'a'*64
        order=[]
        units=[]
        def start_unit(method, value, *a):
            units.append(value);order.append('unit-start')
        bus=SimpleNamespace(call_sync=start_unit)
        gio=SimpleNamespace(BusType=SimpleNamespace(SYSTEM=0),DBusProxy=SimpleNamespace(new_for_bus_sync=lambda *a,**k:bus))
        repository=ModuleType('gi.repository');repository.Gio=gio
        repository.GLib=SimpleNamespace(Variant=lambda signature,value:value)
        gi=ModuleType('gi');gi.repository=repository
        commands=[]
        def run(command,**kwargs):
            commands.append(command)
            if command[0]!='systemctl':order.append('vendor-launch')
            return SimpleNamespace(returncode=3 if command[0]=='systemctl' else 0)
        real_open=builtins.open
        def guarded_open(path,*a,**kwargs):
            if str(path)=='/dev/umts_boot0':raise AssertionError('Parent must not force CP power transitions')
            return real_open(path,*a,**kwargs)
        with patch.object(launcher.argparse.ArgumentParser,'parse_args',return_value=args), \
                patch.object(launcher.os,'geteuid',return_value=0), \
                patch.object(Path,'read_bytes',return_value=b'samsung,star2lte\0'), \
                patch.object(launcher.subprocess,'run',side_effect=run), \
                patch.object(launcher,'load_runtime',return_value=runtime), \
                patch.object(launcher,'verify_private_runtime',side_effect=lambda *a:order.append('validated')), \
                patch.dict(sys.modules,{'gi':gi,'gi.repository':repository}), \
                patch('builtins.open',side_effect=guarded_open):
            with redirect_stdout(io.StringIO()):launcher.main()
        self.assertEqual(order,['validated','unit-start','vendor-launch'])
        properties=dict(units[0][2])
        child=properties['ExecStart'][0][1]
        flag=child.index('--private-rfs-diagnostics')
        self.assertEqual(child[flag+1],str(args.lab_directory/'rfs-diagnostics'))
        runtime.safe_components.assert_called_once_with(args.lab_directory)
        self.assertEqual(sum(c[0]!='systemctl' for c in commands),1)
        tree=ast.parse((ROOT/'scripts/g965n/run-ril-test.py').read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and
               isinstance(n.func,ast.Attribute) and n.func.attr=='ioctl']
        self.assertEqual(len(calls),1)
        self.assertIsInstance(calls[0].args[1],ast.Constant)
        self.assertEqual(calls[0].args[1].value,0x6f27)  # status-only; no power/reset
        self.assertFalse(any(isinstance(n,ast.Constant) and n.value==0x6f20 for n in ast.walk(tree)))

    def test_provenance_and_bind_validation_both_required(self):
        runtime = self.runtime()
        helper = ROOT/'scripts/g965n/vendor-runtime.py'
        self.assertIs(launcher.verify_private_runtime(helper, runtime), runtime)
        runtime.validate_modem_state.assert_called_with({'fixture': True})
        runtime.verify_private_bindings.assert_called_once()
        runtime.read_provenance.side_effect = RuntimeError('legacy refused')
        runtime.verify_private_bindings.reset_mock()
        with self.assertRaisesRegex(RuntimeError, 'legacy'):
            launcher.verify_private_runtime(helper, runtime)
        runtime.verify_private_bindings.assert_not_called()


if __name__ == '__main__': unittest.main()

# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import concurrent.futures
import threading
import time
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('trial', Path(__file__).parents[1] / 'scripts/g965n/mesa-session-trial.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_profile_is_unique_coherent_and_preserves_frozen_build(self):
        build = self.root / 'immutable'
        receipt = {'outputs': {str(build / 'build/src/egl/libEGL_mesa.so.0.0.0'): 'a'*64}, 'runtime_links': {}}
        files, env = m.profile_files(self.root / 'home', 'one', build, receipt)
        self.assertEqual(len(files), 4)
        self.assertEqual(env['PAN_MESA_DEBUG'], 'nocrc,noafbc')
        self.assertEqual(env['MESA_SHADER_CACHE_DISABLE'], 'false')
        self.assertNotIn('MESA_LOADER_DRIVER_OVERRIDE', env)
        self.assertTrue(all(str(p).startswith(str(self.root / 'home')) for p in files))
        self.assertFalse(build.exists())
        wrapper = next(text for path, text in files.items() if path.name == 'shell.py')
        compile(wrapper, 'shell.py', 'exec')
        self.assertIn('MESA_LOADER_DRIVER_OVERRIDE', wrapper)
        self.assertIn("os.execve('/usr/bin/gnome-shell'", wrapper)
        self.assertTrue(any('ExecStart=\nExecStart=' in text for text in files.values()))

    def test_existing_or_symlink_path_rejected(self):
        existing = self.root / 'already'; existing.write_text('owner')
        with self.assertRaises(RuntimeError): m.safe_new(existing)
        link = self.root / 'link'; link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(RuntimeError): m.safe_new(link / 'new')

    def test_cleanup_removes_only_unchanged_owned_files(self):
        good = self.root / 'good'; good.write_text('ours')
        changed = self.root / 'changed'; changed.write_text('owner edit')
        unknown = self.root / 'unknown'; unknown.write_text('keep')
        symlink = self.root / 'link'; symlink.symlink_to(good)
        expected = hashlib.sha256(b'ours').hexdigest()
        result = m.owned_cleanup({str(changed): expected, str(symlink): expected, str(good): expected})
        self.assertEqual(result, [str(changed), str(symlink)])
        self.assertFalse(good.exists()); self.assertEqual(unknown.read_text(), 'keep')
        self.assertEqual(changed.read_text(), 'owner edit'); self.assertTrue(symlink.is_symlink())

    def test_previous_environment_whitelist_and_quoting(self):
        text = "OTHER=private\nLD_LIBRARY_PATH='/old path'\nPAN_MESA_DEBUG=nocrc\n"
        self.assertEqual(m.previous_environment(text), {'LD_LIBRARY_PATH': '/old path', 'PAN_MESA_DEBUG': 'nocrc'})
        with self.assertRaises(RuntimeError): m.previous_environment("LD_PRELOAD=$'bad\\nvalue'")

    def test_timer_reserved_and_checked_before_user_file_and_gdm_writes(self):
        events = []
        home = self.root / 'home'; home.mkdir()
        build = self.root / 'build'
        receipt = {'outputs': {str(build / 'build/src/egl/libEGL_mesa.so.0.0.0'): 'a'*64}, 'runtime_links': {}}
        args = types.SimpleNamespace(trial='test-one', build=build,expected_boot_sha256='b'*64)
        def command(argv, **kw):
            events.append(argv)
            if argv[0] == 'systemd-run' or argv[:2] == ['systemctl','is-active']:
                self.assertFalse((home/'.config').exists())
            return types.SimpleNamespace(stdout='PAN_MESA_DEBUG=nocrc\n')
        with patch.object(m, 'private_root', return_value=True), patch.object(m, 'STATE', self.root/'state'), patch.object(m, 'verify_device'), patch.object(m, 'verify_shell_command'), patch.object(m, 'verify_build', return_value=receipt), patch.object(m.pwd, 'getpwnam', return_value=types.SimpleNamespace(pw_uid=1000,pw_dir=str(home))), patch.object(m, 'run', side_effect=command), patch.object(m.os, 'chown'):
            m.apply(args)
        reserve = next(i for i,v in enumerate(events) if v[0]=='systemd-run')
        check = next(i for i,v in enumerate(events) if v[:2]==['systemctl','is-active'])
        restart = next(i for i,v in enumerate(events) if v==['systemctl','restart','gdm.service'])
        self.assertLess(reserve,check); self.assertLess(check,restart)
        self.assertFalse(any('stop' in v for v in events))
        data=json.loads((self.root/'state/test-one/state.json').read_text())
        self.assertEqual(data['previous_environment'], {'PAN_MESA_DEBUG':'nocrc'})
        self.assertFalse(data['accepted'])

    def test_reservation_failure_never_writes_user_profile(self):
        home=self.root/'home';home.mkdir();build=self.root/'build'
        receipt={'outputs': {str(build/'build/src/egl/libEGL_mesa.so.0.0.0'):'a'*64},'runtime_links':{}}
        args=types.SimpleNamespace(trial='test-two',build=build,expected_boot_sha256='b'*64)
        def command(argv,**kw):
            if argv[0]=='systemd-run':raise RuntimeError('reserve failed')
            return types.SimpleNamespace(stdout='')
        with patch.object(m,'private_root',return_value=True),patch.object(m,'STATE',self.root/'state'),patch.object(m,'verify_device'),patch.object(m,'verify_shell_command'),patch.object(m,'verify_build',return_value=receipt),patch.object(m.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=1000,pw_dir=str(home))),patch.object(m,'run',side_effect=command):
            with self.assertRaises(RuntimeError):m.apply(args)
        self.assertFalse((home/'.config').exists())

    def test_accept_requires_actual_postrestart_evidence(self):
        evidence=self.root/'evidence.json';evidence.write_text(json.dumps({'trial':'one','boot_sha256':'b'*64,'captured_at_unix':2,'fresh_ssh':True}))
        args=types.SimpleNamespace(state=self.root,evidence=evidence)
        with patch.object(m,'load_state',return_value={'accepted':False,'trial':'one','boot_sha256':'b'*64,'staged_at_unix':1}),patch.object(m,'run') as run:
            with self.assertRaises(RuntimeError):m.accept_locked(args)
            run.assert_not_called()

    def test_automatic_accepted_timer_is_noop_but_manual_rollback_restores(self):
        directory=self.root/'state';directory.mkdir()
        state={'accepted':True,'files':{},'previous_environment':{}}
        with patch.object(m,'load_state',return_value=state),patch.object(m,'cleanup_user_files',return_value=[]) as cleanup,patch.object(m,'restore_environment') as restore,patch.object(m,'run') as run:
            m.rollback_locked(directory,automatic=True)
            cleanup.assert_not_called();run.assert_not_called()
            m.rollback_locked(directory,automatic=False)
            cleanup.assert_called_once();restore.assert_called_once_with({})
            run.assert_called_once_with(['systemctl','restart','gdm.service'])
            self.assertTrue(json.loads((directory/'state.json').read_text())['rolled_back'])

    def test_changed_owned_files_preserved_and_reported_after_recovery(self):
        directory=self.root/'state';directory.mkdir()
        state={'accepted':False,'files':{'changed':'hash'},'previous_environment':{}}
        with patch.object(m,'load_state',return_value=state),patch.object(m,'cleanup_user_files',return_value=['changed']),patch.object(m,'restore_environment'),patch.object(m,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'preserved modified'):
                m.rollback_locked(directory)
            run.assert_called_once_with(['systemctl','restart','gdm.service'])
            self.assertEqual(json.loads((directory/'state.json').read_text())['rollback_preserved_changed_files'],['changed'])

    def test_explicit_accept_stops_only_its_timer_after_scoped_evidence(self):
        evidence=self.root/'proof.json';evidence.write_text(json.dumps({'trial':'one','boot_sha256':'b'*64,'captured_at_unix':2,'fresh_ssh':True,'shell_private_dso_maps':True,'kernel_health_reviewed':True}))
        state={'trial':'one','boot_sha256':'b'*64,'staged_at_unix':1,'timer':'g965n-mesa-rollback-one','files':{}}
        args=types.SimpleNamespace(state=self.root,evidence=evidence)
        with patch.object(m,'load_state',return_value=state),patch.object(m,'run') as run,patch.object(m.subprocess,'run',return_value=types.SimpleNamespace(returncode=3)):
            m.accept_locked(args)
            run.assert_called_once_with(['systemctl','stop','g965n-mesa-rollback-one.timer'])
            self.assertTrue(json.loads((self.root/'state.json').read_text())['accepted'])

    def test_atomic_state_failure_keeps_old_restoration_record(self):
        target=self.root/'state.json';target.write_text('{"old":true}')
        with patch.object(m.os,'replace',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):m.write_state(self.root,{'accepted':True})
        self.assertEqual(json.loads(target.read_text()),{'old':True})
        self.assertEqual(list(self.root.glob('.state-*')),[])

    def test_unknown_gpu_override_refused_and_known_baseline_preserved(self):
        m.validate_previous({'PAN_MESA_DEBUG':'nocrc','LD_PRELOAD':''})
        for override in ({'LD_LIBRARY_PATH':'/other'},{'MESA_LOADER_DRIVER_OVERRIDE':'panfrost'},{'PAN_MESA_DEBUG':'unknown'}):
            with self.assertRaises(RuntimeError):m.validate_previous(override)

    def test_profile_write_child_creates_private_directory_chains(self):
        # Exercise emitted child code as this test's ordinary user, without
        # running runuser/systemd or touching a real home directory.
        target=self.root/'fresh/a/b/shell.py'
        with patch.object(m,'user_command',side_effect=lambda argv:argv):
            m.write_user_files({target:'test'})
        self.assertEqual(target.read_text(),'test')
        for path in (target,target.parent,target.parent.parent,self.root/'fresh'):
            self.assertEqual(path.stat().st_uid,m.os.getuid())
            self.assertEqual(path.stat().st_mode & 0o077,0)

    def test_inherited_shell_arguments_must_match_reviewed_command(self):
        exact='{ path=/usr/bin/gnome-shell ; argv[]=/usr/bin/gnome-shell ; ignore_errors=no ; }'
        with patch.object(m,'manager',return_value=types.SimpleNamespace(stdout=exact)):
            m.verify_shell_command()
        for changed in (exact.replace('argv[]=/usr/bin/gnome-shell ;','argv[]=/usr/bin/gnome-shell --wayland ;'),'other-command'):
            with patch.object(m,'manager',return_value=types.SimpleNamespace(stdout=changed)):
                with self.assertRaises(RuntimeError):m.verify_shell_command()

    def test_two_concurrent_trials_reserve_only_one_system_timer(self):
        home=self.root/'home';home.mkdir();build=self.root/'build'
        receipt={'outputs':{str(build/'build/src/egl/libEGL_mesa.so.0.0.0'):'a'*64},'runtime_links':{}}
        barrier=threading.Barrier(2);timers=[]
        def command(argv,**kw):
            if argv[0]=='systemd-run':
                timers.append(argv);time.sleep(.05)
            return types.SimpleNamespace(stdout='PAN_MESA_DEBUG=nocrc\n')
        def attempt(name):
            barrier.wait(timeout=3)
            try:m.apply(types.SimpleNamespace(trial=name,build=build,expected_boot_sha256='b'*64));return 'applied'
            except RuntimeError as error:return str(error)
        with patch.object(m,'private_root',return_value=True),patch.object(m,'STATE',self.root/'state'),patch.object(m,'verify_device'),patch.object(m,'verify_shell_command'),patch.object(m,'verify_build',return_value=receipt),patch.object(m.pwd,'getpwnam',return_value=types.SimpleNamespace(pw_uid=1000,pw_dir=str(home))),patch.object(m,'run',side_effect=command),patch.object(m,'write_user_files'):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(attempt,name) for name in ('first','second')]
                results=[f.result(timeout=4) for f in futures]
        self.assertEqual(results.count('applied'),1)
        self.assertEqual(sum('Another staged or accepted' in r for r in results),1)
        self.assertEqual(len(timers),1)
        self.assertEqual(len(list((self.root/'state').glob('*/state.json'))),1)

    def test_active_vendor_json_is_pinned_and_tampering_prevents_shell_exec(self):
        build=self.root/'immutable';build.mkdir()
        library=build/'libEGL_mesa.so.0.0.0';library.write_bytes(b'test-only-library')
        receipt={'outputs':{str(library):hashlib.sha256(library.read_bytes()).hexdigest()},'runtime_links':{}}
        files,_=m.profile_files(self.root/'home','vendor-pin',build,receipt)
        vendor=next(p for p in files if p.name=='vendor.json');vendor.parent.mkdir(parents=True)
        code=next(text for path,text in files.items() if path.name=='shell.py')
        vendor.write_text(files[vendor])
        with patch.object(m.os,'execve') as execute:
            exec(compile(code,'trial-wrapper','exec'),{})
            execute.assert_called_once()
        vendor.write_text('{"ICD":{"library_path":"/other.so"}}')
        with patch.object(m.os,'execve') as execute:
            with self.assertRaisesRegex(SystemExit,'Trial library changed'):
                exec(compile(code,'trial-wrapper','exec'),{})
            execute.assert_not_called()

    def test_runtime_link_resolving_outside_build_is_rejected(self):
        build=self.root/'build';build.mkdir();outputs={}
        for name in ('libEGL_mesa.so.0.0.0','libgallium-25.2.8.so','libgbm.so.1.0.0','dri_gbm.so'):
            p=build/name;p.write_bytes(b'test');outputs[str(p)]=hashlib.sha256(b'test').hexdigest()
        outside=self.root/'outside';outside.write_bytes(b'test')
        link=build/'libgbm.so';link.symlink_to(outside)
        (build/'receipt.json').write_text(json.dumps({'phase':'built','outputs':outputs,'runtime_links':{str(link):str(outside)}}))
        with self.assertRaisesRegex(RuntimeError,'Build link changed'):m.verify_build(build)


if __name__ == '__main__': unittest.main()

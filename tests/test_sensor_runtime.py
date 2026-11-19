#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Sensor supervisor fault tests; all native/module/vendor calls are mocked."""
import fcntl
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]


def module(path):
    m=types.ModuleType(path.stem);m.__file__=str(path)
    exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m

S=module(ROOT/'scripts/g965n/sensor-runtime.py')
V=module(ROOT/'scripts/g965n/vendor-runtime.py')


class SensorRuntimeTests(unittest.TestCase):
    def test_als_only_default_never_passes_matrix(self):
        for profile in [{},{'accel':{}},{'accel':{'enabled':False}}]:
            params,expected=S.bridge_policy(profile)
            self.assertEqual(params,['enable_g965n=1','enable_accel=0'])
            self.assertNotIn('accel_mount_matrix',expected)

    def test_qualified_accel_flags(self):
        matrix=[1,0,0,0,1,0,0,0,1];S.validate_matrix(matrix)
        params,expected=S.bridge_policy({'accel':{'enabled':True,'mount_matrix':matrix}})
        self.assertEqual(params,['enable_g965n=1','enable_accel=1','accel_mount_matrix=1,0,0,0,1,0,0,0,1'])
        for invalid in [[0]*9,[2,0,0,0,1,0,0,0,1],[1]*8,[True,0,0,0,1,0,0,0,1]]:
            with self.assertRaises(RuntimeError):S.validate_matrix(invalid)

    def test_up_sensors_never_enumerates_or_chowns_modem(self):
        character=types.SimpleNamespace(st_mode=stat.S_IFCHR|0o600,st_rdev=123)
        with mock.patch.object(V,'safe_components'),mock.patch.object(V.os.path,'ismount',return_value=True),mock.patch.object(V.Path,'exists',return_value=True),mock.patch.object(V.Path,'lstat',return_value=character),mock.patch.object(V.Path,'glob',return_value=[Path('/dev/umts_test')]) as glob,mock.patch.object(V.os,'chown') as chown:
            V.device_nodes(include_modem=False)
            glob.assert_not_called();chown.assert_not_called()
            V.device_nodes()
            glob.assert_called_once_with('umts_*');chown.assert_called_once()

    def test_lock_retains_bytes_and_blocks_exclusive_after_downgrade(self):
        real_fstat=os.fstat
        def root_stat(fd):
            st=real_fstat(fd)
            return types.SimpleNamespace(st_mode=st.st_mode,st_uid=0,st_nlink=st.st_nlink)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'lock';p.write_bytes(b'preserve');p.chmod(0o600)
            with mock.patch.object(S.os,'fstat',side_effect=root_stat):
                with S.lock_file(p,fcntl.LOCK_EX) as fd:
                    fcntl.flock(fd,fcntl.LOCK_SH)
                    other=os.open(p,os.O_RDWR)
                    try:
                        with self.assertRaises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    finally:os.close(other)
                self.assertEqual(p.read_bytes(),b'preserve')
                alias=Path(td)/'alias';alias.symlink_to(p)
                with self.assertRaises(OSError):
                    with S.lock_file(alias,fcntl.LOCK_EX):pass
                os.link(p,Path(td)/'hardlink')
                with self.assertRaises(RuntimeError):
                    with S.lock_file(p,fcntl.LOCK_EX):pass

    def test_runtime_unmount_requires_exact_owner_and_quiescent_cgroup(self):
        with tempfile.TemporaryDirectory() as td:
            owner=Path(td)/'owner';owner.write_text('owned')
            boot=Path(td)/'boot';boot.write_text('same-boot')
            value={'schema':1,'profile_sha256':'p','boot_id':'same-boot','mounts':['exact'],'cgroup':'/service','baseline':{'123':'old'}}
            mounts=['exact'];called=[]
            def teardown():called.append('teardown');mounts.clear()
            runtime=types.SimpleNamespace(teardown=teardown)
            with mock.patch.object(S,'OWNER',owner),mock.patch.object(S,'BOOT_ID',boot),mock.patch.object(S,'trusted_bytes',return_value=json.dumps(value).encode()),mock.patch.object(S,'mount_fingerprint',side_effect=lambda:list(mounts)),mock.patch.object(S,'cgroup_members',return_value={'123':'old','777':'new'}) as members:
                with self.assertRaisesRegex(RuntimeError,'child'):S.cleanup_owned(runtime,'p')
                self.assertTrue(owner.exists());self.assertEqual(called,[])
                members.return_value={'123':'old'}
                with self.assertRaises(RuntimeError):S.cleanup_owned(runtime,'wrong-profile')
                self.assertEqual(called,[])
                S.cleanup_owned(runtime,'p')
                self.assertEqual(called,['teardown']);self.assertFalse(owner.exists())

    def test_unowned_mounts_are_preserved(self):
        with tempfile.TemporaryDirectory() as td,mock.patch.object(S,'OWNER',Path(td)/'absent'),mock.patch.object(S,'mount_fingerprint',return_value=['shared']):
            runtime=types.SimpleNamespace(teardown=mock.Mock())
            with self.assertRaisesRegex(RuntimeError,'Unowned'):S.cleanup_owned(runtime,'p')
            runtime.teardown.assert_not_called()

    def test_real_ready_pipe_requires_exact_ack_and_live_children(self):
        child=types.SimpleNamespace(poll=lambda:None)
        S.STOP=False
        for data,success in [(b'READY\n',True),(b'READY\nextra',False),(b'',False)]:
            r,w=os.pipe();os.write(w,data);os.close(w)
            try:
                if success:S.await_ready(child,child,r,1)
                else:
                    with self.assertRaises(RuntimeError):S.await_ready(child,child,r,1)
            finally:os.close(r)

    def test_cleanup_orders_broker_before_lhd_and_continues_after_timeout(self):
        events=[]
        class Child:
            def __init__(self,name,fail=False):self.name=name;self.fail=fail;self.code=None
            def poll(self):return self.code
            def terminate(self):events.append(self.name+' terminate')
            def kill(self):events.append(self.name+' kill')
            def wait(self,timeout):
                events.append(self.name+' wait')
                if self.fail:self.fail=False;raise subprocess.TimeoutExpired('broker',timeout)
                self.code=0;return 0
        r,w=os.pipe()
        try:
            S.stop_children(Child('broker'),Child('lhd'),w,1)
            self.assertEqual(os.read(r,32),b'STOP\n')
            self.assertEqual(events,['broker wait','lhd terminate','lhd wait'])
        finally:os.close(r)
        events.clear()
        with self.assertRaises(RuntimeError):S.stop_children(Child('broker',True),Child('lhd'),None,1)
        self.assertIn('broker kill',events);self.assertEqual(events[-2:],['lhd terminate','lhd wait'])

    def test_broker_fixed_command_no_arbitrary_argv(self):
        p={'programs':{'broker':{'path':'/root/broker.py'}}}
        self.assertEqual(S.broker_command(p,Path('/root/profile'),3,4),['/usr/bin/python3','/root/broker.py','--profile','/root/profile','--sensor-service-child','--ready-fd','3','--stop-fd','4'])

    def test_supervisor_atomic_lease_and_ordered_stop(self):
        self.exercise_supervisor()

    def test_failed_node_creation_revokes_mknod_before_failure_cleanup(self):
        self.exercise_supervisor(fail_nodes=True)

    def exercise_supervisor(self,fail_nodes=False):
        events=[];state={'owned':False,'mounted':False}
        profile={'programs':{'broker':{'path':'/root/broker'}},'vendor':{'lhd_sha256':S.digest(b'vendor'),'config_sha256':S.digest(b'vendor')},'module':{'path':'transport'},'iio_bridge':{'path':'bridge'},'accel':{'enabled':False},'timeouts':{'startup':1,'cleanup':1}}
        def nodes(**kw):
            events.append(('nodes',kw))
            if fail_nodes:raise RuntimeError('node creation failed')
        runtime=types.SimpleNamespace(prepare=lambda **kw:events.append(('prepare',kw)),device_nodes=nodes)
        @contextmanager
        def lock(path,operation):
            events.append(('lock',str(path),operation));yield 777
        class Child:
            def __init__(self,name):self.name=name;self.code=None
            def poll(self):return self.code
            def terminate(self):events.append(self.name+' terminate')
            def wait(self,timeout):events.append(self.name+' wait');self.code=0;return 0
        children=[]
        def launch(argv,**kw):
            name='lhd' if len(children)==0 else 'broker';events.append(name+' start')
            child=Child(name);children.append(child);return child
        def owner(_):state['owned']=True
        def cleanup(*args):
            self.assertTrue(all(child.poll()is not None for child in children));events.append('cleanup');state['owned']=False
        def ready(*args):S.STOP=True;events.append('ready')
        S.STOP=False
        with mock.patch.object(S,'verify_service_unit'),mock.patch.object(S,'load_program',return_value=runtime),mock.patch.object(S,'lock_file',side_effect=lock),mock.patch.object(S,'mount_fingerprint',return_value=[]),mock.patch.object(S,'OWNER',types.SimpleNamespace(exists=lambda:state['owned'])),mock.patch.object(S,'trusted_bytes',return_value=b'vendor'),mock.patch.object(S,'write_owner',side_effect=owner),mock.patch.object(S,'ensure_module',side_effect=lambda *args:events.append('module checked')),mock.patch.object(S,'sensor_view'),mock.patch.object(S,'apply_device_policy',side_effect=lambda **kw:events.append(('policy',kw))),mock.patch.object(S.fcntl,'flock',side_effect=lambda fd,op:events.append(('flock',op))),mock.patch.object(S.subprocess,'Popen',side_effect=launch),mock.patch.object(S,'await_ready',side_effect=ready),mock.patch.object(S,'notify_ready'),mock.patch.object(S,'cleanup_owned',side_effect=cleanup):
            if fail_nodes:
                with self.assertRaisesRegex(RuntimeError,'node creation failed'):
                    S.supervise(profile,Path('/root/profile'),'sha')
            else:S.supervise(profile,Path('/root/profile'),'sha')
        self.assertIn(('prepare',{'sensor_only':True,'create_devices':False}),events)
        self.assertIn(('nodes',{'include_modem':False}),events)
        self.assertLess(events.index(('policy',{'setup':True})),events.index(('nodes',{'include_modem':False})))
        self.assertLess(events.index(('nodes',{'include_modem':False})),events.index(('policy',{'setup':False})))
        if fail_nodes:
            self.assertNotIn('lhd start',events);self.assertNotIn('broker start',events)
            self.assertLess(events.index(('policy',{'setup':False})),events.index('cleanup'))
        else:
            self.assertLess(events.index(('policy',{'setup':False})),events.index('lhd start'))
            self.assertLess(events.index(('flock',fcntl.LOCK_SH)),events.index('lhd start'))
            self.assertLess(events.index('broker wait'),events.index('lhd terminate'))
            self.assertLess(events.index('lhd wait'),events.index(('flock',fcntl.LOCK_EX|fcntl.LOCK_NB)))
        self.assertEqual(events[-1],'cleanup')

    def test_exact_mknod_permission_is_setup_only_and_never_on_partitions(self):
        character=types.SimpleNamespace(st_mode=stat.S_IFCHR|0o600)
        with mock.patch.object(S.Path,'lstat',return_value=character):
            setup=S.sensor_device_allowlist(setup=True)
            running=S.sensor_device_allowlist(setup=False)
        self.assertEqual([p for p,_ in setup],[p for p,_ in running])
        expected_blocks=[('/dev/sda10','r'),('/dev/sda18','r'),('/dev/sda19','r')]
        self.assertEqual(setup[:3],expected_blocks);self.assertEqual(running[:3],expected_blocks)
        self.assertTrue(all(mode=='rwm' for _,mode in setup[3:]))
        self.assertTrue(all(mode=='rw' for _,mode in running[3:]))
        for path,_ in setup:
            self.assertNotIn('umts',path)
            self.assertNotIn(path,['/dev/sda3','/dev/sdd1','/dev/sda12','char-misc'])

    def test_prepare_optional_false_creates_no_devices_and_default_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);root=base/'root';root.mkdir()
            (base/'SYSTEM/system/bin').mkdir(parents=True)
            (base/'SYSTEM/system/apex/com.android.runtime.release').mkdir(parents=True)
            for create in [False,True]:
                for name in ['bin','etc']:
                    if (root/name).is_symlink():(root/name).unlink()
                with mock.patch.object(V,'BASE',base),mock.patch.object(V,'ROOT',root),mock.patch.object(V,'STATE',base/'state'),mock.patch.object(V,'DATA',base/'data'),mock.patch.object(V,'assert_board'),mock.patch.object(V,'safe_directory'),mock.patch.object(V,'private_state'),mock.patch.object(V,'safe_components'),mock.patch.object(V.os.path,'ismount',return_value=False),mock.patch.object(V,'mount'),mock.patch.object(V,'run'),mock.patch.object(V.subprocess,'check_output',side_effect=['SYSTEM','VENDOR']),mock.patch.object(V,'device_nodes') as nodes:
                    if create:V.prepare(sensor_only=True)
                    else:V.prepare(sensor_only=True,create_devices=False)
                    if create:nodes.assert_called_once_with(include_modem=False)
                    else:nodes.assert_not_called()

    def test_structured_policy_update_forwards_setup_then_runtime_permissions(self):
        calls=[]
        bus=types.SimpleNamespace(call_sync=lambda *args:calls.append(args))
        gio=types.SimpleNamespace(BusType=types.SimpleNamespace(SYSTEM=1),DBusProxy=types.SimpleNamespace(new_for_bus_sync=lambda *args:bus))
        glib=types.SimpleNamespace(Variant=lambda signature,value:(signature,value))
        repository=types.ModuleType('gi.repository');repository.Gio=gio;repository.GLib=glib
        package=types.ModuleType('gi');package.repository=repository
        character=types.SimpleNamespace(st_mode=stat.S_IFCHR|0o600)
        with mock.patch.dict(sys.modules,{'gi':package,'gi.repository':repository}),mock.patch.object(S,'verify_service_unit') as verify,mock.patch.object(S.Path,'lstat',return_value=character):
            S.apply_device_policy(setup=True);S.apply_device_policy(setup=False)
        self.assertEqual(verify.call_count,2)
        for call,mode in zip(calls,['rwm','rw']):
            self.assertEqual(call[0],'SetUnitProperties')
            signature,(unit,temporary,properties)=call[1]
            self.assertEqual((signature,unit,temporary),('(sba(sv))',S.UNIT,True))
            policy=dict(properties)
            self.assertEqual(policy['DevicePolicy'],('s','closed'))
            allowed=policy['DeviceAllow'][1]
            self.assertTrue(all(value=='r' for _,value in allowed[:3]))
            self.assertTrue(all(value==mode for _,value in allowed[3:]))

    def test_profile_als_and_qualified_accel_gates_before_startup(self):
        names=b'\0.shstrtab\0.modinfo\0'
        info=b'vermagic=7.1.0-dirty SMP preempt mod_unload aarch64\0'
        raw=bytearray(256);raw[:7]=b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HH',raw,16,1,183);struct.pack_into('<Q',raw,40,64);struct.pack_into('<HHH',raw,58,64,3,1)
        for index,n,start,length in [(1,1,256,len(names)),(2,11,256+len(names),len(info))]:
            struct.pack_into('<I',raw,64+64*index,n);struct.pack_into('<QQ',raw,64+64*index+24,start,length)
        ko=bytes(raw)+names+info
        def entry(name,data):return {'path':'/root/'+name,'sha256':S.digest(data),'bytes':len(data)}
        backup={'model':'SM-G965N','complete':True,'partitions':[{'name':n,'bytes':1,'sha256':'a'*64} for n in sorted(S.PARTITIONS)]}
        kernel={'boot_sha256':'b'*64,'built_in_iio':True,'kernel_release':'7.1.0-dirty','modules':{name:{'bytes':len(ko),'sha256':S.digest(ko)} for name in ('sensors','iio-bridge')}}
        profile={'schema':1,'model':'SM-G965N','programs':{n:entry(n,b'self') for n in ['supervisor','runtime','kernel_verifier','broker','ssp_probe']},'backup_manifest':entry('backup',json.dumps(backup).encode()),'kernel_receipt':entry('kernel',json.dumps(kernel).encode()),'expected_boot_sha256':'b'*64,'module':entry('transport',ko),'iio_bridge':{**entry('bridge',ko),'device':'/dev/g965n-iio-bridge'},'hub_patch':{'path':str(Path('/lib/firmware/g965n/bcm4773-patch.bin').resolve()),'sha256':S.digest(b'patch')},'accel':{'enabled':False},'identity':{'chip_id':1,'firmware':2,'sensor_mask':3},'timeouts':{'startup':60,'cleanup':25}}
        data={'/root/backup':json.dumps(backup).encode(),'/root/kernel':json.dumps(kernel).encode(),'/root/transport':ko,'/root/bridge':ko,profile['hub_patch']['path']:b'patch'}
        check=mock.Mock()
        def input_data(e,*args,**kwargs):return data.get(e['path'],b'self')
        with mock.patch.object(S,'pinned',side_effect=input_data),mock.patch.object(S,'trusted_bytes',return_value=b'self'),mock.patch.object(S,'load_program',return_value=types.SimpleNamespace(verify_kernel=check)):
            self.assertEqual(S.validate_profile(profile),kernel)
            self.assertTrue(check.called)
            profile['accel']={'enabled':True,'range_g':8,'mount_matrix':[1,0,0,0,1,0,0,0,1]}
            with self.assertRaises(KeyError):S.validate_profile(profile)
            proof={'model':'SM-G965N','range_g':8,'mount_matrix':profile['accel']['mount_matrix'],'status':'verified','geometry_validated':True}
            profile['orientation_evidence']=entry('orientation',b'proof');data['/root/orientation']=json.dumps(proof).encode()
            S.validate_profile(profile)
            proof['geometry_validated']=False;data['/root/orientation']=json.dumps(proof).encode()
            with self.assertRaisesRegex(RuntimeError,'Orientation'):S.validate_profile(profile)
            profile['accel']={'enabled':False}
            with self.assertRaisesRegex(RuntimeError,'ALS-only'):S.validate_profile(profile)

    def test_device_policy_requires_own_mainpid_and_exact_cgroup(self):
        good=f'Id={S.UNIT}\nMainPID={os.getpid()}\nControlGroup=/system.slice/{S.UNIT}\nDevicePolicy=closed\n'
        with mock.patch.object(S.subprocess,'check_output',return_value=good),mock.patch.object(S,'cgroup_path',return_value='/system.slice/'+S.UNIT):S.verify_service_unit()
        for bad in [good.replace(str(os.getpid()),'999999'),good.replace('DevicePolicy=closed','DevicePolicy=auto'),good.replace('ControlGroup=/system.slice/','ControlGroup=/other/')]:
            with mock.patch.object(S.subprocess,'check_output',return_value=bad),mock.patch.object(S,'cgroup_path',return_value='/system.slice/'+S.UNIT):
                with self.assertRaises(RuntimeError):S.verify_service_unit()

    def test_incomplete_module_elf_rejected(self):
        for value in [b'',bytes(64)]:
            with self.assertRaises(RuntimeError):S.elf_section(value,'.modinfo')


if __name__=='__main__':unittest.main()

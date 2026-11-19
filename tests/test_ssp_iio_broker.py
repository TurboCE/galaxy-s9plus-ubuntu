# SPDX-License-Identifier: GPL-2.0-only
import contextlib
import importlib.util
import os
import io
import json
from pathlib import Path
import stat
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('broker',ROOT/'scripts/g965n/ssp-iio-broker.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class BrokerTests(unittest.TestCase):
    def test_magnetic_trial_is_opt_in_private_bounded_and_accel_qualified(self):
        p={'accel':{'enabled':True}}
        self.assertIsNone(b.magnetic_capture_policy(p))
        valid={'output':'/var/lib/g965n-sensors/magnetic-trials/one.jsonl','seconds':60}
        p['magnetic_capture']=valid
        self.assertEqual(b.magnetic_capture_policy(p),valid)
        for update in ({'seconds':True},{'seconds':601},{'seconds':0},
                       {'output':'/home/ubuntu/one.jsonl'},
                       {'output':'/var/lib/g965n-sensors/magnetic-trials/../one.jsonl'}):
            with self.assertRaises(ValueError):
                b.magnetic_capture_policy({**p,'magnetic_capture':{**valid,**update}})
        with self.assertRaises(ValueError):
            b.magnetic_capture_policy({**p,'accel':{'enabled':False}})

    def test_magnetic_capture_records_actual_batches_expires_and_limits_size(self):
        c=b.MagneticCapture.__new__(b.MagneticCapture)
        c.stream=io.StringIO();c.bytes=0;c.deadline=12
        self.assertTrue(c.record({0:[(1,2,3)],4:[]},10))
        value=json.loads(c.stream.getvalue())
        self.assertEqual(value,{'receive_monotonic_s':10,'samples':{'0':[[1,2,3]]}})
        self.assertFalse(c.record({4:[(4,5,6,2,0)]},12))
        self.assertNotIn('heading',value)
        c.bytes=2*1024*1024
        with self.assertRaisesRegex(RuntimeError,'size bound'):c.record({4:[(4,5,6,2,0)]},11)

    def test_magnetic_trial_does_not_publish_a_heading_into_iio(self):
        q=types.SimpleNamespace(samples={0:[(1,2,3)],4:[(4,5,6,2,0)],9:[]})
        feed=types.SimpleNamespace(publish=unittest.mock.Mock());seen=set()
        b.publish_actual(q,[0,9,4],feed,seen,None,1)
        feed.publish.assert_called_once_with(1,(1,2,3))
        self.assertEqual(seen,{0,4});self.assertEqual(q.samples[4],[])

    def test_initial_not_ready_is_bounded_receive_only_wait(self):
        ready=unittest.mock.Mock(side_effect=[RuntimeError('Hub transport not ready; no sensor enabled'),None])
        ssp=types.SimpleNamespace(require_transport_ready=ready)
        with patch.object(b.select,'select',return_value=([],[],[])):
            self.assertTrue(b.wait_transport(ssp,types.SimpleNamespace(fd=55,requested=lambda:False),lambda:False,1))
        self.assertEqual(ready.call_count,2)
        ready.reset_mock();self.assertFalse(b.wait_transport(ssp,types.SimpleNamespace(fd=55,requested=lambda:True),lambda:False,1));ready.assert_not_called()
        ready.side_effect=RuntimeError('Hub transport not ready; no sensor enabled')
        with self.assertRaisesRegex(RuntimeError,'deadline'):
            b.wait_transport(ssp,types.SimpleNamespace(fd=55,requested=lambda:False),lambda:False,0)

    def test_wire_layout_actual_values_and_heartbeat(self):
        frames=[]
        with patch.object(b.os,'write',side_effect=lambda fd,data:frames.append(data) or len(data)):
            f=b.Feed(55);f.publish(2,(391,0,0));f.publish(3);f.publish(1,(-32768,0,32767))
        decoded=[b.FRAME.unpack(x) for x in frames]
        self.assertEqual(len(frames[0]),48)
        self.assertEqual(decoded[0],(1,48,1,2,0,391,0,0,0,0,0))
        self.assertEqual(decoded[2][2:8],(3,1,1,-32768,0,32767))

    def test_invalid_or_short_frame_does_not_advance(self):
        f=b.Feed(1)
        with patch.object(b.os,'write') as write:
            for kind,values in [(2,(-1,0,0)),(2,(1,False,0)),(1,(32768,0,0)),(9,(0,0,0)),(3,(1,0,0))]:
                with self.assertRaises(ValueError):f.publish(kind,values)
            write.assert_not_called();self.assertEqual(f.seq,0)
        with patch.object(b.os,'write',return_value=47):
            with self.assertRaises(RuntimeError):f.publish(3)
        self.assertEqual(f.seq,0)
        f.seq=0xffffffffffffffff
        with self.assertRaises(OverflowError):f.publish(3)

    def test_empty_samples_are_not_zero_samples(self):
        q=types.SimpleNamespace(samples={9:[]});feed=types.SimpleNamespace(publish=unittest.mock.Mock());seen=set()
        self.assertIsNone(b.publish_actual(q,[9],feed,seen,None,1))
        feed.publish.assert_not_called();self.assertFalse(seen)
        q.samples[9]=[(0,1,2)]
        b.publish_actual(q,[9],feed,seen,None,2)
        feed.publish.assert_called_once_with(2,(0,0,0));self.assertEqual(seen,{9})

    def test_unselected_records_do_not_accumulate(self):
        q=types.SimpleNamespace(samples={9:[],1:[(1,2,3)]*1000})
        feed=types.SimpleNamespace(publish=unittest.mock.Mock())
        b.publish_actual(q,[9],feed,set(),None,1)
        self.assertEqual(q.samples[1],[]);feed.publish.assert_not_called()

    def run_fixture(self,light=True,accel=False,cleanup_error=False):
        now=[0.0];commands=[];disabled=[];frames=[];closed=[]
        rready,wready=os.pipe();rstop,wstop=os.pipe();os.set_blocking(rready,False)
        self.addCleanup(lambda:[os.close(fd) for fd in (rready,wready,rstop,wstop)])
        real_write=os.write;real_close=os.close
        class Probe:
            def __init__(self,layout):self.fd=778;self.samples={0:[],9:[]};self.unparsed=0;self.pumps=0
            def transaction(self,command,payload=b'',length=0):
                commands.append((command,payload,length))
                if command==0xE1:return b'\x08'
                if command==0xA1 and payload[0]==9 and light:self.samples[9]=[(68,4397,1,2,3,4,17,64)]
                if command==0xA1 and payload[0]==0:self.samples[0]=[(0,-4096,0)]
                return b''
            def pump(self,seconds):
                now[0]+=.5;self.pumps+=1
                if light and not accel and self.pumps==3:real_write(wstop,b'STOP\n')
        def disable(q,enabled):
            disabled.extend(enabled)
            if cleanup_error:raise RuntimeError('cleanup test')
        ssp=types.SimpleNamespace(Probe=Probe,SAMPLE_DELAY_MS=200,acquire_probe_lock=contextlib.nullcontext,
            acquire_hub_identity=lambda q:{'chip_id':85,'firmware':21031900,'sensor_mask':513},
            require_advertised=lambda selected,mask:None,require_transport_ready=lambda:None,disable_sensors=disable)
        profile={'accel':{'enabled':accel},'identity':{'chip_id':85,'firmware':21031900,'sensor_mask':513},'timeouts':{'startup':1}}
        def write(fd,data):
            if fd==777:frames.append(b.FRAME.unpack(data));return len(data)
            return real_write(fd,data)
        def close(fd):
            if fd in (777,778):closed.append(fd)
            else:real_close(fd)
        with patch.object(b.signal,'signal'),patch.object(b.time,'monotonic',side_effect=lambda:now[0]), \
             patch.object(b.os,'open',return_value=777),patch.object(b.os,'fstat',return_value=types.SimpleNamespace(st_mode=stat.S_IFCHR|0o600,st_uid=0)), \
             patch.object(b.os,'write',side_effect=write),patch.object(b.os,'close',side_effect=close):
            error=None
            try:b.run(profile,ssp,wready,rstop)
            except RuntimeError as e:error=str(e)
        try:ready=os.read(rready,128)
        except BlockingIOError:ready=b''
        return commands,disabled,frames,closed,ready,error

    def test_als_only_first_real_value_ready_and_no_acceleration_commands(self):
        commands,disabled,frames,closed,ready,error=self.run_fixture()
        self.assertIsNone(error);self.assertEqual(ready,b'READY\n');self.assertEqual(disabled,[9])
        self.assertEqual(commands,[(0xA1,b'\x09\xc8\0\0\0\0\0\0\0\0',0)])
        self.assertEqual([f[3] for f in frames].count(2),1)
        self.assertNotIn(1,[f[3] for f in frames]);self.assertEqual(set(closed),{777,778})

    def test_no_real_als_never_ready_or_fake_zero(self):
        _,disabled,frames,closed,ready,error=self.run_fixture(light=False)
        self.assertIn('No actual first',error);self.assertEqual(ready,b'')
        self.assertTrue(all(f[3]==3 for f in frames));self.assertEqual(disabled,[9]);self.assertEqual(set(closed),{777,778})

    def test_cleanup_failure_still_closes_bridge_and_transport(self):
        *_,closed,ready,error=self.run_fixture(cleanup_error=True)
        self.assertEqual(error,'cleanup test');self.assertEqual(set(closed),{777,778})

    def test_heartbeat_cannot_hide_stale_acceleration(self):
        commands,disabled,frames,closed,ready,error=self.run_fixture(accel=True)
        self.assertIn('acceleration stream became stale',error);self.assertEqual(ready,b'READY\n')
        self.assertEqual(disabled,[0,9]);self.assertIn((0xE1,b'',1),commands)
        self.assertEqual(set(closed),{777,778})

if __name__=='__main__':unittest.main()

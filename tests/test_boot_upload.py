# SPDX-License-Identifier: GPL-2.0-only
"""Production upload recovery, identity checks, and late-completion safety."""
import ast
import contextlib
import hashlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

SOURCE=Path(__file__).resolve().parents[1]/'scripts/flash/flash_s9plus_boot_adb.py'

class BootUpload(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.image=Path(self.directory.name)/'fixture.img';self.data=b'synthetic boot fixture';self.image.write_bytes(self.data)
        self.digest=hashlib.sha256(self.data).hexdigest();self.remote_hash=None;self.raw_discard=False;self.legacy_hash=self.digest
        self.wait_failures=0;self.loader='G965Nfixture';self.legacy_late_error=False
        self.transport=Mock(side_effect=self.adb)
        self.process=Mock(SubprocessError=subprocess.SubprocessError)
        self.process.run.side_effect=self.raw
        nodes=[n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('upload_boot','require')]
        self.env={'subprocess':self.process,'adb':self.transport,'ADB':'fixture-adb','SERIAL':'selected-fixture-device'}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),self.env)

    def raw(self,*args,**kwargs):
        self.assertEqual(kwargs['stdin'].read(),self.data)
        if not self.raw_discard:self.remote_hash=self.digest

    def adb(self,*args,**kwargs):
        if args[0]=='shell':
            command=args[1]
            if command.startswith('sha256sum'):
                if self.remote_hash is None:raise subprocess.CalledProcessError(1,'fixture')
                return self.remote_hash+'  fixture'
            return {'getprop ro.product.device':'star2lte','getprop ro.bootloader':self.loader,'id -u':'0'}[command]
        if args[0]=='get-state':return 'recovery'
        if args[0]=='wait-for-recovery' and self.wait_failures:
            self.wait_failures-=1;raise subprocess.TimeoutExpired('fixture',45)
        if args[0]=='push':
            self.remote_hash=self.legacy_hash
            if self.legacy_late_error:raise subprocess.CalledProcessError(1,'fixture')
        return ''

    def upload(self,prefer_sync=False):
        with contextlib.redirect_stdout(io.StringIO()):
            self.env['upload_boot'](self.image,'/tmp/fixture.img',self.digest,'G965Nfixture',prefer_sync=prefer_sync)

    def test_verified_staging_reused(self):
        self.remote_hash=self.digest;self.upload();self.process.run.assert_not_called();self.assertEqual(self.transport.call_count,1)

    def test_preferred_uncompressed_sync_avoids_raw_channel(self):
        self.upload(prefer_sync=True);self.process.run.assert_not_called()
        self.assertTrue(any(c.args[:2]==('push','-Z') for c in self.transport.call_args_list))

    def test_raw_selected_transfer_and_recovery_verified(self):
        self.upload();self.assertEqual(self.process.run.call_args.args[0][:4],['fixture-adb','-s','selected-fixture-device','exec-in'])
        self.assertFalse(any(c.args[0]=='push' for c in self.transport.call_args_list))

    def test_completed_raw_survives_transient_offline_without_retransfer(self):
        self.wait_failures=1;self.upload();self.assertEqual(self.process.run.call_count,1)
        self.assertEqual(sum(c.args[0]=='wait-for-recovery' for c in self.transport.call_args_list),2)
        self.assertFalse(any(c.args[0]=='push' for c in self.transport.call_args_list))

    def test_discarded_raw_falls_back_and_completed_sync_error_rechecked(self):
        self.raw_discard=True;self.legacy_late_error=True;self.upload()
        self.assertEqual(sum(c.args[0]=='push' for c in self.transport.call_args_list),1)

    def test_bad_legacy_hash_aborts_before_partition_write(self):
        self.raw_discard=True;self.legacy_hash='bad'
        with self.assertRaisesRegex(SystemExit,'no partition write performed'):self.upload()
        self.assertFalse(any('dd ' in str(c) or 'reboot' in str(c) for c in self.transport.call_args_list))

    def test_model_change_after_reconnect_aborts(self):
        self.loader='different'
        with self.assertRaisesRegex(SystemExit,'identity changed'):self.upload()
        self.assertFalse(any(c.args[0]=='push' for c in self.transport.call_args_list))

if __name__=='__main__':unittest.main()

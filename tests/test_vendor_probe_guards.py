# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts/g965n'/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
runner=load('vendor_probe_runner','run-vendor-probe.py')
build=load('vendor_probe_builder','build-vendor-probe.py')


class VendorProbeTests(unittest.TestCase):
    def test_wrong_model_missing_consent_and_nonroot_stop_before_helpers(self):
        for model,root,backup,consent in (('other',0,True,True),('SM-G965N',501,True,True),
                ('SM-G965N',0,False,True),('SM-G965N',0,True,False)):
            args=SimpleNamespace(model=model,confirm_backup_verified=backup,consent_readonly_probe=consent)
            with patch.object(runner.os,'geteuid',return_value=root),patch.object(runner,'checked_module') as helper:
                with self.assertRaises(ValueError):runner.run(args)
                helper.assert_not_called()

    def test_private_lab_cannot_escape_data_or_inject_unit_name(self):
        data=Path('/private/data')
        self.assertEqual(runner.lab_relative(data/'probe-1',data),Path('probe-1'))
        for lab in (Path('relative'),Path('/outside/probe'),data/'a/../b',data/'a/b',data/'bad name',data):
            with self.assertRaises(ValueError):runner.lab_relative(lab,data)

    def test_helper_digest_verified_before_execution_and_links_refused(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'helper.py';p.write_text('raise AssertionError("must not execute")\n')
            with self.assertRaises(ValueError):runner.checked_module(p,'0'*64)
            p.write_text('answer=7\n');h=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(runner.checked_module(p,h).answer,7)
            link=p.with_name('link.py');link.symlink_to(p)
            with self.assertRaises(ValueError):runner.checked_module(link,h)

    def test_raw_logs_identifiers_and_nonboolean_records_never_surface(self):
        raw='private raw text\n{"imei":"synthetic-private"}\n{"readonly_self_test":1,"ril_init_called":false}\n'
        raw+='{"readonly_self_test":true,"ril_init_called":false,"extra":"private"}\n'
        raw+='{"readonly_self_test":true,"ril_init_called":false}\n'
        self.assertEqual(runner.safe_records(raw,'self-test'),[{'readonly_self_test':True,'ril_init_called':False}])
        self.assertEqual(runner.safe_records(raw,'inspect'),[])

    def test_owner_abi_tamper_and_missing_uapi_fail_before_build_output(self):
        with tempfile.TemporaryDirectory() as name:
            d=Path(name);inputs=d/'owner';inputs.mkdir();out=d/'output'
            elf=bytearray(64);elf[:6]=b'\x7fELF\x02\x01';elf[18:20]=(183).to_bytes(2,'little')
            p=inputs/'libc.so';p.write_bytes(elf);h=hashlib.sha256(elf).hexdigest()
            with patch.object(build,'PINS',{'libc.so':h}):
                build.checked_inputs(inputs)
                with patch.object(build.subprocess,'run') as compiler:
                    with self.assertRaises(ValueError):build.build(inputs,d/'headers',out)
                    compiler.assert_not_called();self.assertFalse(out.exists())
                p.write_bytes(b'wrong')
                with self.assertRaises(ValueError):build.checked_inputs(inputs)
                p.unlink();p.symlink_to(d/'missing')
                with self.assertRaises(ValueError):build.checked_inputs(inputs)


if __name__=='__main__':unittest.main()

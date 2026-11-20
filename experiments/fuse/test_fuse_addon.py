#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import contextlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import types
import unittest
from unittest import mock


def get(name):
    p=Path(__file__).with_name(name+'.py');m=types.ModuleType(name)
    m.__file__=str(p);exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m

B=get('build-addon');L=get('load-once')


def elf(arch=183,license='GPL',vermagic=None,depends=''):
    if vermagic is None:vermagic=B.RELEASE+' SMP preempt mod_unload aarch64 '
    names=b'\0.shstrtab\0.modinfo\0'
    info=('name=fuse\0license='+license+'\0vermagic='+vermagic+'\0depends='+depends+'\0').encode()
    raw=bytearray(64+192)
    raw[:7]=b'\x7fELF\x02\x01\x01'
    struct.pack_into('<HH',raw,16,1,arch);struct.pack_into('<Q',raw,40,64)
    struct.pack_into('<HHH',raw,58,64,3,1)
    for index,name,start,length in [(1,1,256,len(names)),(2,11,256+len(names),len(info))]:
        struct.pack_into('<I',raw,64+64*index,name)
        struct.pack_into('<QQ',raw,64+64*index+24,start,length)
    return bytes(raw)+names+info


class FuseTests(unittest.TestCase):
    def test_module_abi(self):
        self.assertEqual(B.module_info(elf())['name'],['fuse'])
        for data in [b'',elf(arch=62),elf(license='Proprietary'),elf(vermagic='wrong'),elf(depends='foreign'),elf()[:-1]]:
            with self.subTest(length=len(data)):
                with self.assertRaises((ValueError,UnicodeDecodeError)):B.module_info(data)

    def test_elf_section_bounds(self):
        raw=bytearray(elf());struct.pack_into('<Q',raw,40,2**63)
        with self.assertRaises(ValueError):B.module_info(raw)
        raw=bytearray(elf());struct.pack_into('<Q',raw,64+128+32,2**63)
        with self.assertRaises(ValueError):B.module_info(raw)

    def test_backup_guard(self):
        backup={'model':'SM-G965N','complete':True,'partitions':[{'name':n,'bytes':1,'sha256':'a'*64} for n in sorted(L.PARTITIONS)]}
        raw=json.dumps(backup).encode();L.validate_backup(raw,L.sha(raw))
        with self.assertRaises(ValueError):L.validate_backup(raw,'b'*64)
        backup['partitions'].append(backup['partitions'][0]);raw=json.dumps(backup).encode()
        with self.assertRaises(ValueError):L.validate_backup(raw,L.sha(raw))

    def fixture(self):
        module=elf();config=b'test-config\n';startup=json.dumps({'boot_sha256':'b'*64}).encode()
        backup=json.dumps({'model':'SM-G965N','complete':True,'partitions':[{'name':n,'bytes':1,'sha256':'a'*64} for n in sorted(L.PARTITIONS)]}).encode()
        r={'schema':1,'model':'SM-G965N','kernel':json.loads(startup),'startup_sha256':L.sha(startup),
           'loader_sha256':L.sha(b'loader'),'backup_manifest_sha256':L.sha(backup),
           'verify_kernel_sha256':L.sha(b'verifier'),'recipe_file_sha256':L.sha(b'recipe'),
           'native_config_sha256':L.sha(config),'module':{'bytes':len(module),'sha256':L.sha(module),'modinfo':B.module_info(module)}}
        files={'startup.json':startup,'backup.json':backup,'load-once.py':b'loader','verify-kernel.py':b'verifier','build-addon.py':b'recipe'}
        return module,config,r,files

    def execute(self,fail=None):
        module,config,r,files=self.fixture()
        if fail=='module':r['module']['sha256']='0'*64
        raw=json.dumps(r).encode();files['receipt.json']=raw
        calls=[]
        deploy=types.SimpleNamespace(verify_kernel=lambda receipt:calls.append('verify_kernel'))
        recipe=types.SimpleNamespace(CONFIG_SHA=r['native_config_sha256'],module_info=B.module_info)
        def checked(name,data,expected):
            self.assertEqual(L.sha(data),expected)
            return deploy if name=='kernel_verifier' else recipe
        with tempfile.TemporaryFile() as f:
            f.write(module);f.flush()
            def module_fd(path):return os.dup(f.fileno())
            with mock.patch.object(L.os,'geteuid',return_value=0),mock.patch.object(L,'read',side_effect=lambda p:files[p.name]),mock.patch.object(L,'safe_open',side_effect=module_fd),mock.patch.object(L,'checked_module',side_effect=checked),mock.patch.object(L.gzip,'open',return_value=io.BytesIO(b'wrong' if fail=='config' else config)),mock.patch.object(L.Path,'exists',return_value=False),mock.patch.object(L.subprocess,'run',side_effect=lambda args,**kw:calls.append(args)),contextlib.redirect_stdout(io.StringIO()):
                if fail:
                    with self.assertRaises(ValueError):L.perform(Path('/private'),'0'*64 if fail=='receipt' else L.sha(raw),'b'*64,True,True,'SM-G965N')
                else:L.perform(Path('/private'),L.sha(raw),'b'*64,True,True,'SM-G965N')
        return calls

    def test_verify_before_one_insmod(self):
        calls=self.execute();self.assertEqual(calls[0],'verify_kernel');self.assertEqual(len(calls),2)
        self.assertEqual(calls[1][0],'/usr/sbin/insmod');self.assertEqual(len(calls[1]),2)
        self.assertTrue(calls[1][1].startswith('/proc/self/fd/'))

    def test_failures_do_not_load(self):
        for error in ['receipt','config','module']:
            with self.subTest(error=error):self.assertFalse(any(isinstance(x,list) for x in self.execute(error)))

    def test_explicit_consent_before_io(self):
        with mock.patch.object(L.os,'geteuid',return_value=0),mock.patch.object(L,'read') as read:
            for backup,consent,model in [(False,True,'SM-G965N'),(True,False,'SM-G965N'),(True,True,'SM-G965F')]:
                with self.assertRaises(ValueError):L.perform(Path('/private'),'a'*64,'b'*64,backup,consent,model)
            read.assert_not_called()


if __name__=='__main__':unittest.main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute the build's actual pre-Image contract; never build or access a device."""
import gzip
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BUILD=(ROOT/'scripts/build/build71.sh').read_text()
CHECK=BUILD.split("<<'INITRAMFS_CONTRACT'\n",1)[1].split('\nINITRAMFS_CONTRACT',1)[0]


class InitramfsContractTests(unittest.TestCase):
    def check(self,mode='boot',change=None):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);ramfs=root/'ramfs';device=root/'device'
            ramfs.mkdir();device.mkdir();(root/'out').mkdir()
            boot=b'#!/bin/sh\nexec switch_root /newroot /sbin/init\n'
            probe=b'#!/bin/sh\necho probe\n'
            (device/'mainline-init-boot').write_bytes(boot)
            (device/'mainline-init').write_bytes(probe)
            init=ramfs/'init';init.write_bytes(boot if mode=='boot' else probe);init.chmod(0o755)
            config={'CONFIG_BLK_DEV_INITRD':'y','CONFIG_INITRAMFS_FORCE':'y','CONFIG_CMDLINE_FORCE':'y',
                    'CONFIG_INITRAMFS_SOURCE':'"'+str(ramfs)+'"'}
            if change in config:config[change]='n' if change!='CONFIG_INITRAMFS_SOURCE' else '""'
            if change=='wrong_init':init.write_bytes(b'wrong entry')
            if change=='not_executable':init.chmod(0o644)
            if change=='empty_init':init.write_bytes(b'')
            if change=='symlink_init':
                init.unlink();init.symlink_to(device/'mainline-init-boot')
            (root/'out/.config').write_text('\n'.join(k+'='+v for k,v in config.items())+'\n')
            return subprocess.run([sys.executable,'-c',CHECK,str(ramfs),str(device),mode],cwd=root,capture_output=True,text=True)

    def test_real_build_contract_accepts_boot_and_probe(self):
        for mode in ['boot','probe']:
            with self.subTest(mode=mode):self.assertEqual(self.check(mode).returncode,0)

    def test_fail_closed_before_image(self):
        for change in ['CONFIG_BLK_DEV_INITRD','CONFIG_INITRAMFS_FORCE','CONFIG_CMDLINE_FORCE',
                       'CONFIG_INITRAMFS_SOURCE','wrong_init','not_executable','empty_init','symlink_init']:
            with self.subTest(change=change):self.assertNotEqual(self.check(change=change).returncode,0)

    def test_check_after_final_kconfig_before_build(self):
        start=BUILD.index('# BEGIN G965N BUILTIN INITRAMFS CONTRACT')
        self.assertLess(BUILD.rfind('make -s O=out olddefconfig'),start)
        self.assertLess(start,BUILD.index('O=out Image dtbs'))
        self.assertIn('cfg --enable INITRAMFS_FORCE',BUILD)
        self.assertIn('cfg --enable CMDLINE_FORCE',BUILD)
        # Existing placeholder-producing commands remain in the wrapper paths.
        self.assertIn("printf '' | gzip -n > blob/ramdisk",(ROOT/'scripts/build/build_uniloader.sh').read_text())
        self.assertIn('gzip.compress(b"", compresslevel=9, mtime=0)',(ROOT/'scripts/build/pack_uniloader.sh').read_text())

    def test_actual_existing_wrapper_has_empty_gzip_not_cpio(self):
        path=Path(os.environ.get('G965N_WRAPPER_BOOT',str(ROOT/'dist/uniloader/boot-g965n-experimental-20261118T205213Z.img')))
        if not path.exists():self.skipTest('supply existing private wrapper BOOT using G965N_WRAPPER_BOOT')
        before=path.read_bytes();self.assertEqual(before[:8],b'ANDROID!')
        kernel,size,page=(struct.unpack_from('<I',before,n)[0] for n in [8,16,36])
        start=page+(kernel+page-1)//page*page;ramdisk=before[start:start+size]
        self.assertEqual(len(ramdisk),20);self.assertEqual(gzip.decompress(ramdisk),b'')
        self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()

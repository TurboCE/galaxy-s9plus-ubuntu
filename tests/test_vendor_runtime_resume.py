# SPDX-License-Identifier: GPL-2.0-only
"""Private-state provenance, fail-closed resume and content-preserving migration."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vendor_runtime_resume', ROOT/'scripts/g965n/vendor-runtime.py')
vr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vr)


class PrivateRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.state = self.base/'state'; self.state.mkdir(mode=0o700)
        self.runtime_base = self.base/'runtime'; self.runtime_base.mkdir(mode=0o700)
        self.runtime = self.runtime_base/'root'; self.runtime.mkdir()
        (self.runtime/'dev').mkdir()
        self.data = self.state/'data'; self.data.mkdir()
        self.compatible = self.base/'compatible'; self.compatible.write_bytes(b'samsung,star2lte\0samsung,exynos9810\0')
        self.original = self.base/'original'; self.original.mkdir()
        self.specs = {}
        for name, size, byte in [('EFS',4096,b'e'),('CPEFS',2048,b'c'),('RADIO',1024,b'r')]:
            file = self.original/(name+'.img'); file.write_bytes(byte*size)
            self.specs[name] = (file,size)
        self.fingerprints = {name:{'node':str(file),'bytes':size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
                             for name,(file,size) in self.specs.items()}
        self.manifest = self.original/'manifest.json'
        self.manifest.write_text(json.dumps({'model':'SM-G965N','bootloader':'G965NTEST1','complete':True,
            'partitions':[dict(name=name,bytes=f['bytes'],sha256=f['sha256']) for name,f in self.fingerprints.items()] +
                         [dict(name=name,bytes=16,sha256='f'*64) for name in vr.BACKUP_PARTITIONS-set(self.fingerprints)]}))
        self.nv = bytes(range(256))*2
        self.make_clones()
        self.patches = [patch.object(vr,'BASE',self.runtime_base), patch.object(vr,'ROOT',self.runtime),
                        patch.object(vr,'STATE',self.state), patch.object(vr,'DATA',self.data),
                        patch.object(vr,'ROOT_UID',os.geteuid()), patch.object(vr,'COMPATIBLE',self.compatible),
                        patch.object(vr,'PARTITION_SPECS',self.specs),
                        patch.object(vr,'partition_fingerprints',side_effect=lambda:copy.deepcopy(self.fingerprints)),
                        patch.object(vr,'assert_modem_stopped'),
                        patch.object(vr.os.path,'ismount',side_effect=lambda p:Path(p)==self.runtime),
                        patch.object(vr,'device_nodes'), patch.object(vr,'cbd_permissions')]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.mounts=[]; self.commands=[]
        def fake_mount(source,target,*options):
            Path(target).mkdir(parents=True,exist_ok=True)
            self.mounts.append((str(source),str(target),options))
        def fake_run(*args):
            self.commands.append(tuple(map(str,args)))
            if args[0]=='debugfs':
                target=Path(str(args[2]).split(' ',2)[2])
                self.populate(target,target.name)
        self.run_patch=patch.object(vr,'run',side_effect=fake_run);self.run_patch.start();self.addCleanup(self.run_patch.stop)
        self.mount_patch=patch.object(vr,'mount',side_effect=fake_mount);self.mount_patch.start();self.addCleanup(self.mount_patch.stop)
        self.receipt = dict(schema=1,model='SM-G965N',bootloader='G965NTEST1',source=copy.deepcopy(self.fingerprints),
                            backup_manifest_sha256=hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
                            backup_sha256={k:v['sha256'] for k,v in self.fingerprints.items()},
                            initial_nv=vr.verify_nv(self.state/'efs'))
        vr.write_private_json(self.state/vr.RECEIPT_NAME,self.receipt)

    def populate(self,target,name):
        if name=='efs':
            (target/'nv_data.bin').write_bytes(self.nv)
            (target/'nv_data.bin.md5').write_text(hashlib.md5(self.nv+vr.SALT).hexdigest())
            (target/'identity.fixture').write_bytes(b'synthetic same-handset fixture')
        else:(target/'calibration.fixture').write_bytes(b'synthetic calibration')

    def make_clones(self):
        for name in ('efs','cpefs'):
            d=self.state/name;d.mkdir();self.populate(d,name)
        (self.state/'RADIO').write_bytes(self.specs['RADIO'][0].read_bytes())

    def assert_no_binding(self):
        self.assertEqual(self.mounts,[])
        self.assertFalse(any(c[0]=='mount' for c in self.commands))

    def test_resume_preserves_valid_evolved_nv_and_never_extracts_or_copies(self):
        changed=bytes(reversed(self.nv))
        (self.state/'efs/nv_data.bin').write_bytes(changed)
        (self.state/'efs/nv_data.bin.md5').write_text(hashlib.md5(changed+vr.SALT).hexdigest())
        before={p:p.read_bytes() for p in self.state.rglob('*') if p.is_file()}
        with patch.object(vr.shutil,'copyfileobj',side_effect=AssertionError('resume must not copy')):
            vr.resume_modem()
        self.assertEqual({p:p.read_bytes() for p in before},before)
        self.assertEqual([m[0] for m in self.mounts],[str(self.state/'efs'),str(self.state/'cpefs')])
        binds=[c for c in self.commands if c[0]=='mount']
        self.assertIn(('mount','--bind',str(self.state/'RADIO'),str(self.runtime/'dev/block/platform/11120000.ufs/by-name/RADIO')),binds)
        self.assertIn(('mount','-o','remount,bind,ro',str(self.runtime/'dev/block/platform/11120000.ufs/by-name/RADIO')),binds)
        self.assertFalse(any(str(file) in str(self.mounts)+str(binds) for file,_ in self.specs.values()))
        self.assertEqual((self.runtime/'efs').readlink(),Path('/mnt/vendor/efs'))

    def test_child_revalidates_attested_receipt_after_enqueue_gap(self):
        expected = vr.launch_receipt_digest()
        with patch.object(vr, 'verify_private_bindings') as bindings:
            vr.validate_launch_state(expected)
            bindings.assert_called_once()
            # A migration publishes a new receipt before queued service starts.
            receipt = self.state / vr.RECEIPT_NAME
            receipt.write_text(receipt.read_text() + ' ')
            bindings.reset_mock()
            with self.assertRaisesRegex(RuntimeError, 'changed since'):
                vr.validate_launch_state(expected)
            bindings.assert_not_called()

    def test_child_rejects_changed_nv_and_radio_even_with_same_receipt(self):
        expected = vr.launch_receipt_digest()
        with patch.object(vr, 'verify_private_bindings') as bindings:
            (self.state / 'efs/nv_data.bin').write_bytes(b'x'*len(self.nv))
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                vr.validate_launch_state(expected)
            bindings.assert_not_called()
            self.populate(self.state / 'efs', 'efs')
            (self.state / 'RADIO').write_bytes(b'x'*1024)
            with self.assertRaisesRegex(RuntimeError, 'RADIO'):
                vr.validate_launch_state(expected)
            bindings.assert_not_called()

    def test_shared_lock_blocks_exclusive_and_never_truncates(self):
        lock = self.base / 'runtime.lock'
        lock.write_bytes(b'preserved'); lock.chmod(0o600)
        with patch.object(vr, 'RUNTIME_LOCK', lock):
            with vr.shared_runtime_lock():
                other = os.open(lock, os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError):
                        vr.fcntl.flock(other, vr.fcntl.LOCK_EX | vr.fcntl.LOCK_NB)
                finally:
                    os.close(other)
            self.assertEqual(lock.read_bytes(), b'preserved')
            lock.chmod(0o644)
            with self.assertRaisesRegex(RuntimeError, 'lock file'):
                with vr.shared_runtime_lock(): self.fail('Public lock must fail')

    def test_runtime_binds_require_same_private_inode_and_readonly(self):
        radio = self.runtime / 'dev/block/platform/11120000.ufs/by-name/RADIO'
        radio.parent.mkdir(parents=True); radio.write_bytes(b'fixture')
        for name in ('system', 'vendor', 'mnt/vendor/efs', 'mnt/vendor/cpefs'):
            (self.runtime / name).mkdir(parents=True)
        with patch.object(vr.os.path, 'ismount', return_value=True), \
                patch.object(vr.os.path, 'samefile', return_value=True), \
                patch.object(vr.os, 'statvfs', return_value=type('Flags', (), {'f_flag':os.ST_RDONLY})()):
            vr.verify_private_bindings()
            with patch.object(vr.os.path, 'samefile', return_value=False):
                with self.assertRaisesRegex(RuntimeError, 'private copy'): vr.verify_private_bindings()
            with patch.object(vr.os, 'statvfs', return_value=type('Flags', (), {'f_flag':0})()):
                with self.assertRaisesRegex(RuntimeError, 'read-only'): vr.verify_private_bindings()

    def test_snapshot_pins_verified_bytes_before_debugfs(self):
        source = self.specs['EFS'][0]
        expected = self.fingerprints['EFS']
        with vr.verified_backup_snapshot(source, expected) as snapshot:
            self.assertNotEqual(snapshot, source)
            self.assertEqual(stat.S_IMODE(snapshot.parent.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(snapshot.stat().st_mode), 0o400)
            source.write_bytes(b'x' * expected['bytes'])
            self.assertEqual(vr.digest(snapshot), expected['sha256'])
        self.assertFalse(snapshot.exists())
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            with vr.verified_backup_snapshot(source, expected):
                self.fail('Changed backup must never be extracted')

    def test_archive_preserves_binary_receipt_and_metadata(self):
        receipt = self.state / vr.RECEIPT_NAME
        receipt.write_bytes(b'\xff\x00legacy opaque receipt\x80')
        receipt.chmod(0o600)
        before = vr.file_inventory(receipt)
        vr.archive_modem_state(self.specs['EFS'][0], self.specs['CPEFS'][0], self.manifest, True)
        archive = next(self.state.glob('archive-*'))
        self.assertEqual(vr.file_inventory(archive / vr.RECEIPT_NAME), before)
        self.assertEqual((archive / vr.RECEIPT_NAME).read_bytes(), b'\xff\x00legacy opaque receipt\x80')

    def test_archive_detects_receipt_mutation_after_move(self):
        rename = Path.rename
        def corrupt(source, target):
            result = rename(source, target)
            if source.name == vr.RECEIPT_NAME:
                Path(target).write_bytes(b'changed after move')
            return result
        with patch.object(Path, 'rename', corrupt):
            with self.assertRaisesRegex(RuntimeError, 'Receipt archive verification'):
                vr.archive_modem_state(self.specs['EFS'][0], self.specs['CPEFS'][0], self.manifest, True)
        archive = next(self.state.glob('archive-*'))
        self.assertTrue((archive / 'efs/nv_data.bin').exists())
        self.assertTrue((archive / vr.RECEIPT_NAME).exists())

    def test_permission_walk_rejects_links_without_touching_outside(self):
        outside = self.base / 'outside-permission'
        outside.write_bytes(b'preserve'); outside.chmod(0o640)
        (self.state / 'efs/escape').symlink_to(outside)
        with self.assertRaises(OSError):
            vr.private_permissions(self.state / 'efs', os.geteuid(), os.getegid(), 0o700, 0o600)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o640)

    def test_receiptless_legacy_state_is_not_automatically_adopted(self):
        (self.state/vr.RECEIPT_NAME).unlink()
        with self.assertRaisesRegex(RuntimeError,'legacy'):
            vr.resume_modem()
        self.assert_no_binding()
        self.assertEqual((self.state/'efs/nv_data.bin').read_bytes(),self.nv)

    def test_model_or_original_hash_mismatch_fails_before_binding(self):
        for field,value in [('model','SM-G965F'),('bootloader','G965FTEST1')]:
            bad=copy.deepcopy(self.receipt);bad[field]=value
            (self.state/vr.RECEIPT_NAME).write_text(json.dumps(bad))
            with self.assertRaises(RuntimeError):vr.resume_modem()
            self.assert_no_binding()
        (self.state/vr.RECEIPT_NAME).write_text(json.dumps(self.receipt))
        self.fingerprints['EFS']['sha256']='0'*64
        with self.assertRaises(RuntimeError):vr.resume_modem()
        self.assert_no_binding()

    def test_radio_size_hash_symlink_and_nv_checksum_fail_closed(self):
        radio=self.state/'RADIO';original=radio.read_bytes()
        for bad in [original[:-1],b'x'*len(original)]:
            radio.write_bytes(bad)
            with self.assertRaises(RuntimeError):vr.resume_modem()
            self.assert_no_binding()
        radio.unlink();radio.symlink_to(self.specs['RADIO'][0])
        with self.assertRaises(RuntimeError):vr.resume_modem()
        self.assert_no_binding()
        radio.unlink();radio.write_bytes(original)
        (self.state/'efs/nv_data.bin.md5').write_text('0'*32)
        with self.assertRaisesRegex(RuntimeError,'checksum'):vr.resume_modem()
        self.assert_no_binding()

    def test_private_tree_links_special_files_and_oversize_are_rejected(self):
        bad=self.state/'efs/escape';bad.symlink_to(self.original)
        with self.assertRaises(RuntimeError):vr.resume_modem()
        bad.unlink()
        outside=self.base/'outside';outside.write_bytes(b'not a clone')
        os.link(outside,bad)
        with self.assertRaises(RuntimeError):vr.resume_modem()
        bad.unlink()
        if hasattr(os,'mkfifo'):
            os.mkfifo(bad)
            with self.assertRaises(RuntimeError):vr.resume_modem()
            bad.unlink()
        bad.write_bytes(b'x'*5000)
        with self.assertRaisesRegex(RuntimeError,'partition bound'):vr.resume_modem()
        self.assert_no_binding()

    def test_symlink_ancestor_or_runtime_redirect_is_rejected_before_mount(self):
        real=self.base/'real-efs';(self.state/'efs').rename(real);(self.state/'efs').symlink_to(real)
        with self.assertRaises(RuntimeError):vr.resume_modem()
        self.assert_no_binding()
        (self.state/'efs').unlink();real.rename(self.state/'efs')
        (self.runtime/'efs').symlink_to('/unexpected')
        with self.assertRaises(RuntimeError):vr.resume_modem()
        self.assert_no_binding()

    def test_malformed_or_public_provenance_is_rejected(self):
        path=self.state/vr.RECEIPT_NAME
        for mutate in [lambda r:r.update(schema=2),lambda r:r.pop('backup_sha256'),lambda r:r.update(initial_nv={'bytes':512})]:
            bad=copy.deepcopy(self.receipt);mutate(bad);path.write_text(json.dumps(bad))
            with self.assertRaises(RuntimeError):vr.resume_modem()
            self.assert_no_binding()
        path.write_text(json.dumps(self.receipt));path.chmod(0o640)
        with self.assertRaises(RuntimeError):vr.resume_modem()
        self.assert_no_binding()

    def test_live_clients_and_existing_bindings_are_preserved(self):
        with patch.object(vr,'assert_modem_stopped',side_effect=RuntimeError('active')):
            with self.assertRaises(RuntimeError):vr.resume_modem()
        self.assert_no_binding()
        with patch.object(vr.os.path,'ismount',side_effect=lambda p:Path(p) in [self.runtime,self.runtime/'mnt/vendor/efs']):
            with self.assertRaises(RuntimeError):vr.resume_modem()
        self.assert_no_binding()

    def test_stage_requires_verified_images_and_records_private_origin(self):
        for name in ('efs','cpefs'):shutil.rmtree(self.state/name)
        (self.state/'RADIO').unlink();(self.state/vr.RECEIPT_NAME).unlink()
        with self.assertRaisesRegex(RuntimeError,'manifest'):
            vr.stage_modem(self.specs['EFS'][0],self.specs['CPEFS'][0])
        self.assert_no_binding()
        vr.stage_modem(self.specs['EFS'][0],self.specs['CPEFS'][0],self.manifest)
        receipt=json.loads((self.state/vr.RECEIPT_NAME).read_text())
        self.assertEqual(receipt['source'],self.fingerprints)
        self.assertEqual(receipt['backup_manifest_sha256'],hashlib.sha256(self.manifest.read_bytes()).hexdigest())
        self.assertEqual(stat.S_IMODE((self.state/vr.RECEIPT_NAME).stat().st_mode),0o600)
        self.assertEqual((self.state/'efs/nv_data.bin').read_bytes(),self.nv)
        self.assertEqual(sum(c[0]=='debugfs' for c in self.commands),2)

    def test_stage_does_not_overwrite_existing_private_state(self):
        before=(self.state/'efs/nv_data.bin').read_bytes()
        with self.assertRaisesRegex(RuntimeError,'Preserve'):
            vr.stage_modem(self.specs['EFS'][0],self.specs['CPEFS'][0],self.manifest)
        self.assertEqual((self.state/'efs/nv_data.bin').read_bytes(),before)
        self.assert_no_binding()

    def test_partial_manifest_cannot_be_promoted_to_complete_provenance(self):
        m=json.loads(self.manifest.read_text());m['partitions']=[e for e in m['partitions'] if e['name']!='RECOVERY']
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(RuntimeError,'nine-partition'):
            vr.backup_provenance(self.specs['EFS'][0],self.specs['CPEFS'][0],self.manifest)
        self.assert_no_binding()

    def test_modified_backup_fails_before_extraction(self):
        for name in ('efs','cpefs'):shutil.rmtree(self.state/name)
        (self.state/'RADIO').unlink();(self.state/vr.RECEIPT_NAME).unlink()
        self.specs['EFS'][0].write_bytes(b'x'*4096)
        with self.assertRaises(RuntimeError):
            vr.stage_modem(self.specs['EFS'][0],self.specs['CPEFS'][0],self.manifest)
        self.assertFalse((self.state/'efs').exists());self.assertEqual(self.commands,[])

    def test_archive_preserves_all_contents_metadata_and_does_not_adopt(self):
        before={name:vr.tree_inventory(self.state/name) for name in ('efs','cpefs')}
        originals={p:p.read_bytes() for p,_ in self.specs.values()}
        with self.assertRaises(RuntimeError):
            vr.archive_modem_state(self.specs['EFS'][0],self.specs['CPEFS'][0],self.manifest)
        vr.archive_modem_state(self.specs['EFS'][0],self.specs['CPEFS'][0],self.manifest,confirm=True)
        archives=list(self.state.glob('archive-*'));self.assertEqual(len(archives),1)
        d=archives[0]
        for name in ('efs','cpefs'):
            self.assertEqual(vr.tree_inventory(d/name),before[name]);self.assertFalse((self.state/name).exists())
        self.assertEqual((d/'RADIO').read_bytes(),self.specs['RADIO'][0].read_bytes())
        self.assertEqual(json.loads((d/'archive-inventory.json').read_text())['origin'],'preserved-not-adopted')
        self.assertFalse((self.state/vr.RECEIPT_NAME).exists())
        with self.assertRaisesRegex(RuntimeError,'legacy'):vr.resume_modem()
        self.assertEqual({p:p.read_bytes() for p in originals},originals)
        self.assert_no_binding()

    def test_original_identity_mount_is_refused_before_any_hash_or_bind(self):
        # Exercise the real mount guard using regular test files as stand-in nodes.
        # st_rdev=0 yields0:0; no actual block device is ever opened by this test.
        self.patches[7].stop()
        info=self.base/'mountinfo';info.write_text('1 0 0:0 / /original rw - ext4 fixture rw\n')
        labels={str(path):name for name,(path,_) in self.specs.items()}
        def output(args,**kwargs):
            if args[0]=='lsblk':return labels[args[-1]]+'\n'
            return str(self.specs[labels[args[-1]]][1])+'\n'
        with patch.object(vr,'MOUNTINFO',info),patch.object(vr.stat,'S_ISBLK',return_value=True),\
             patch.object(vr.subprocess,'check_output',side_effect=output),patch.object(vr,'digest') as hashed:
            with self.assertRaisesRegex(RuntimeError,'mounted'):vr.partition_fingerprints()
            hashed.assert_not_called()
        self.assert_no_binding()

    def test_source_radio_wrong_size_is_refused_before_hashing(self):
        self.patches[7].stop()
        info=self.base/'mountinfo';info.write_text('')
        labels={str(path):name for name,(path,_) in self.specs.items()}
        def output(args,**kwargs):
            if args[0]=='lsblk':return labels[args[-1]]+'\n'
            name=labels[args[-1]]
            return str(self.specs[name][1]+(1 if name=='RADIO' else 0))+'\n'
        with patch.object(vr,'MOUNTINFO',info),patch.object(vr.stat,'S_ISBLK',return_value=True),\
             patch.object(vr.subprocess,'check_output',side_effect=output),patch.object(vr,'digest') as hashed:
            with self.assertRaisesRegex(RuntimeError,'size mismatch'):vr.partition_fingerprints()
            hashed.assert_not_called()
        self.assert_no_binding()

    def test_block_stat_zero_size_does_not_skip_actual_short_read_check(self):
        from types import SimpleNamespace
        path=self.specs['RADIO'][0]
        actual=path.stat()
        block=SimpleNamespace(st_mode=stat.S_IFBLK,st_size=0,st_dev=actual.st_dev,
                              st_ino=actual.st_ino,st_mtime_ns=actual.st_mtime_ns)
        with patch.object(vr.os,'fstat',return_value=block):
            self.assertEqual(vr.digest(path,1024),self.fingerprints['RADIO']['sha256'])
            with self.assertRaisesRegex(RuntimeError,'Short'):vr.digest(path,1025)



if __name__=='__main__':unittest.main()

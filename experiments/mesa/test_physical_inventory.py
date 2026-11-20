#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check accepted-overlay inventory parsing without executing wrapper code."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('physical', Path(__file__).with_name('physical-session.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.build = self.root / 'build'
        self.build.mkdir()
        self.files = {}
        for name in ['libEGL.so', 'libgallium.so', 'libgbm.so', 'backend.so', 'build-vendor.json']:
            p = self.build / name
            p.write_text('pinned-' + name)
            self.files[str(p)] = sha(p)
        self.vendor = self.root / 'vendor.json'
        self.vendor.write_text('{}')
        self.files[str(self.vendor)] = sha(self.vendor)
        self.link = self.build / 'libEGL.so.0'
        self.link.symlink_to('libEGL.so')
        self.wrapper = self.root / 'shell.py'
        self.accepted = {'candidate_build': str(self.build), 'files': {str(self.vendor): sha(self.vendor)}}
        self.write_wrapper()

    def write_wrapper(self):
        self.wrapper.write_text('files=' + repr(self.files) + '\nlinks=' + repr({str(self.link): self.link.readlink().as_posix()}) + '\nraise AssertionError("Wrapper must never be executed")\n')
        self.accepted['files'][str(self.wrapper)] = sha(self.wrapper)

    def test_pinned_constants_only(self):
        result = m.accepted_overlay_inventory(self.accepted, self.build)
        self.assertEqual(len(result['outputs']), 5)
        self.assertNotIn(str(self.vendor), result['outputs'])

    def test_changed_wrapper_rejected(self):
        self.wrapper.write_text('files={}\nlinks={}\n')
        with self.assertRaises(RuntimeError):
            m.accepted_overlay_inventory(self.accepted, self.build)

    def test_changed_output_rejected(self):
        (self.build / 'libEGL.so').write_text('changed')
        with self.assertRaises(RuntimeError):
            m.accepted_overlay_inventory(self.accepted, self.build)

    def test_escaping_link_rejected(self):
        self.link.unlink()
        self.link.symlink_to('../outside.so')
        self.write_wrapper()
        with self.assertRaises(RuntimeError):
            m.accepted_overlay_inventory(self.accepted, self.build)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build isolated Mesa diagnostics. Never install, launch graphics, or access a device."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
VERSION = '25.2.8'
ARCHIVE = 'mesa-' + VERSION + '.tar.xz'
SOURCE_URL = 'https://archive.mesa3d.org/' + ARCHIVE
SOURCE_SHA = '097842f3e49d996868b38688db87b006f7d4541e93ce86d2f341d8b3e7be7c93'
MESON_VERSION = '1.4.1'
PATCH = ROOT / 'experiments/mesa/0001-panfrost-check-explicit-modifier-support.patch'
PATCH_SHA = 'cddfef5672d8fb927cb2ab15ea6753d931e04b49da504bfde94b10cc212b4bbc'
NEON_PATCH = ROOT / 'experiments/mesa/0002-mesa-neon-ubyte4-swizzle.patch'
TILE_PATCH = ROOT / 'experiments/mesa/0003-panfrost-neon-tile32.patch'
TILE_PATCH_SHA = '42e7ca68a115a74504ae7ad09e1a775cd92a40675a08e73c0a378fc6efdd133b'
TILE_SOURCE_SHA = {'input': '52a59ca79214b1e1f96aa7bd23d071c1e93a03b956717cb95f875c40ed6b299e', 'output': '014ff51d653cd0d4f1d6ba41548e75cde042cf04940e570b587ad1060216c844'}
NEON_PATCH_SHA = 'cd95fe92bc4e78dab8caaad98fb9741006cb994036963a16c75d68d7d147b65e'
FORMAT_SHA = {'baseline': '43db67a2f1e33f38931bb4be82506689c000651c0f6d986e457ed5ca98d8405c',
              'neon': '1d8367b70698a89f47f64201021591cc38db450a1d1364cb0cd5fdd1c8a5288f'}
RESOURCE_SHA = {'baseline': '445916b95a284b4f49d76491d60143754976bc7deacabbf4df3bfc56ad7f7eeb',
                'patched': 'ba87b87903b99dc75848c4a297fb0cbee5008ef126a0357caa6677068808d605',
                'neon': 'ba87b87903b99dc75848c4a297fb0cbee5008ef126a0357caa6677068808d605',
                'neon-tile32': 'ba87b87903b99dc75848c4a297fb0cbee5008ef126a0357caa6677068808d605'}
OPTIONS = ['--buildtype=debugoptimized', '--wrap-mode=nodownload', '-Dplatforms=wayland',
           '-Degl-native-platform=wayland', '-Dgallium-drivers=panfrost', '-Dvulkan-drivers=',
           '-Dglx=disabled', '-Dglvnd=enabled', '-Degl=enabled', '-Dgbm=enabled',
           '-Dlibgbm-external=false', '-Dgles1=disabled', '-Dgles2=enabled', '-Dopengl=true',
           '-Dllvm=enabled', '-Dshared-llvm=enabled', '-Dgallium-rusticl=false',
           '-Dgallium-va=disabled', '-Dgallium-vdpau=disabled', '-Dvideo-codecs=',
           '-Dbuild-tests=false', '-Dtools=']


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Expected an ordinary input/output file: ' + str(path))
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


def private_dir(path):
    for item in [path] + list(path.parents):
        if item.is_symlink():
            raise RuntimeError('Work paths must not contain symlinks')
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError('Use a dedicated user-owned mode0700 work directory')


def tree_digest(root):
    h = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        relative = str(path.relative_to(root))
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            if not path.resolve().is_relative_to(root.resolve()):
                raise RuntimeError('Source link escapes its private tree')
            value = ['link', relative, os.readlink(path)]
        elif stat.S_ISREG(mode):
            value = ['file', relative, stat.S_IMODE(mode), digest(path)]
        elif stat.S_ISDIR(mode):
            value = ['directory', relative, stat.S_IMODE(mode)]
        else:
            raise RuntimeError('Unexpected special source file')
        h.update(json.dumps(value, separators=(',', ':')).encode() + b'\n')
    return h.hexdigest()


def save(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    temporary.replace(path)


def inputs(variant):
    if variant in ('patched', 'neon', 'neon-tile32') and (PATCH_SHA is None or digest(PATCH) != PATCH_SHA):
        raise RuntimeError('The reviewed diagnostic patch hash is not pinned or has drifted')
    if variant in ('neon', 'neon-tile32') and digest(NEON_PATCH) != NEON_PATCH_SHA:
        raise RuntimeError('The reviewed NEON patch drifted')
    if variant == 'neon-tile32' and digest(TILE_PATCH) != TILE_PATCH_SHA:
        raise RuntimeError('The reviewed tile patch drifted')
    return {'source_url': SOURCE_URL, 'source_sha256': SOURCE_SHA, 'variant': variant,
            'patch_sha256': PATCH_SHA if variant in ('patched', 'neon', 'neon-tile32') else None,
            'tile_patch_sha256': TILE_PATCH_SHA if variant == 'neon-tile32' else None,
            'neon_patch_sha256': NEON_PATCH_SHA if variant in ('neon', 'neon-tile32') else None,
            'builder_sha256': digest(Path(__file__).resolve()), 'meson_version': MESON_VERSION,
            'meson_options': OPTIONS, 'system': platform.system(), 'machine': platform.machine()}


def extract(archive, destination):
    with tarfile.open(archive, 'r:xz') as stream:
        members = stream.getmembers()
        if len(members) > 100000 or sum(m.size for m in members) > 2 * 1024**3:
            raise RuntimeError('Unexpected source archive size')
        if any(Path(m.name).parts[0] != 'mesa-' + VERSION or m.islnk() or
               not (m.isfile() or m.isdir() or m.issym()) for m in members):
            raise RuntimeError('Unexpected archive paths or inode types')
        stream.extractall(destination, members=members, filter='data')


def clean_build_env():
    env = dict(os.environ)
    for key in ['LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT', 'PKG_CONFIG_PATH',
                'PKG_CONFIG_LIBDIR', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS',
                'CC', 'CXX', 'AR', 'MESON_ARGS', 'DESTDIR']:
        env.pop(key, None)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def tools(meson):
    meson = meson.expanduser().absolute()
    venv = meson.parent.parent
    cfg = venv / 'pyvenv.cfg'
    if not cfg.is_file() or venv.stat().st_uid != os.getuid() or str(venv).startswith(('/usr/', '/opt/', '/etc/')):
        raise RuntimeError('Provide Meson from a private, user-owned virtual environment')
    if subprocess.check_output([str(meson), '--version'], text=True).strip() != MESON_VERSION:
        raise RuntimeError('Expected exact private Meson ' + MESON_VERSION)
    result = {'meson': {'path': str(meson), 'sha256': digest(meson)}, 'venv_cfg_sha256': digest(cfg)}
    for name in ['cc', 'c++', 'ninja', 'pkg-config', 'llvm-config-18']:
        executable = shutil.which(name)
        if executable is None:
            raise RuntimeError('Missing prerequisite (nothing was installed): ' + name)
        p = Path(executable).resolve()
        version = subprocess.check_output([str(p), '--version'], text=True, env=clean_build_env()).splitlines()[0]
        result[name] = {'path': str(p), 'sha256': digest(p), 'version': version}
    if not result['llvm-config-18']['version'].startswith('18.'):
        raise RuntimeError('Expected the LLVM18 toolchain')
    return result


def verify(root, receipt, expected):
    if receipt['inputs'] != expected or tree_digest(root / ('mesa-' + VERSION)) != receipt['source_tree_sha256']:
        raise RuntimeError('Inputs/source drifted; preserve this work tree and choose a new work directory')


def make_launcher(root, receipt):
    build = root / 'build'
    vendor = build / 'src/egl/devenv_glvnd_egl.json'
    egl = Path(json.loads(vendor.read_text())['ICD']['library_path'])
    if not egl.is_absolute() or not egl.resolve().is_relative_to(build):
        raise RuntimeError('EGL JSON must reference this build, never a system vendor')
    required = [egl.resolve(), build / 'src/gallium/targets/dri/libgallium-25.2.8.so',
                (build / 'src/gbm/libgbm.so').resolve(), build / 'src/gbm/backends/dri/dri_gbm.so', vendor]
    receipt['outputs'] = {str(p): digest(p) for p in required}
    library_dirs = [str(build / p) for p in ['src/egl', 'src/gallium/targets/dri', 'src/gbm']]
    receipt['runtime_links'] = {str(p): os.readlink(p) for directory in library_dirs
                                for p in Path(directory).glob('*.so*') if p.is_symlink()}
    environment = {'__EGL_VENDOR_LIBRARY_FILENAMES': str(vendor),
                   'LD_LIBRARY_PATH': ':'.join(library_dirs),
                   'GBM_BACKENDS_PATH': str(build / 'src/gbm/backends/dri'),
                   'LIBGL_DRIVERS_PATH': str(build / 'src/gallium/targets/dri'),
                   'MESA_SHADER_CACHE_DISABLE': 'true'}
    # This launcher is emitted, never executed by the builder. Only its child
    # receives private library selection; it verifies all five coherent inputs.
    code = '#!/usr/bin/env python3\nimport os,sys,json,hashlib\nfrom pathlib import Path\n'
    code += 'files = ' + repr(receipt['outputs']) + '\nlinks = ' + repr(receipt['runtime_links']) + '\nenvironment = ' + repr(environment) + '\n'
    code += "for name, expected in files.items():\n p=Path(name)\n if hashlib.sha256(p.read_bytes()).hexdigest()!=expected: raise SystemExit('Diagnostic build output drifted')\n"
    code += "for name, target in links.items():\n p=Path(name)\n if not p.is_symlink() or os.readlink(p)!=target: raise SystemExit('Diagnostic library link drifted')\n"
    code += "args=sys.argv[1:];args=args[1:] if args[:1]==['--'] else args\nif not args: raise SystemExit('Provide an explicitly authorized Wayland test command')\n"
    code += "env=dict(os.environ)\nfor name in ['LD_PRELOAD','LD_AUDIT','__EGL_VENDOR_LIBRARY_DIRS','LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','MESA_LOADER_DRIVER_OVERRIDE']: env.pop(name,None)\nenv.update(environment)\nos.execvpe(args[0],args,env)\n"
    launcher = root / 'launch.py'
    launcher.write_text(code)
    launcher.chmod(0o700)
    receipt['launcher_sha256'] = digest(launcher)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'configure', 'build', 'verify', 'self-test'])
    p.add_argument('--variant', choices=['baseline', 'patched', 'neon', 'neon-tile32'])
    p.add_argument('--work-dir', type=Path)
    p.add_argument('--mesa-archive', type=Path)
    p.add_argument('--meson', type=Path)
    p.add_argument('--jobs', type=int, choices=[1, 2], default=2)
    args = p.parse_args()
    if args.action == 'self-test':
        result = unittest.main(argv=[sys.argv[0]], exit=False).result
        raise SystemExit(0 if result.wasSuccessful() else 1)
    if os.geteuid() == 0:
        p.error('Run as a normal user; no root operation is part of this builder')
    if sys.version_info < (3, 12) or not args.work_dir or not args.variant:
        p.error('Python3.12+, --work-dir and --variant are required')
    work = args.work_dir.expanduser().absolute()
    private_dir(work)
    with (work / '.builder.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        root = work / args.variant
        expected = inputs(args.variant)
        path = root / 'receipt.json'
        if args.action == 'prepare' and not path.exists():
            if root.exists():
                raise RuntimeError('Partial/unrecognized work tree exists; preserve it and use a new work directory')
            archive = (args.mesa_archive or work / 'cache' / ARCHIVE).expanduser().absolute()
            if digest(archive) != SOURCE_SHA:
                raise RuntimeError('Mesa archive SHA256 mismatch')
            private_dir(root)
            extract(archive, root)
            resource = root / ('mesa-' + VERSION) / 'src/gallium/drivers/panfrost/pan_resource.c'
            if digest(resource) != RESOURCE_SHA['baseline']:
                raise RuntimeError('Pristine pan_resource.c does not match the reviewed source')
            if args.variant in ('patched', 'neon', 'neon-tile32'):
                subprocess.run(['patch', '--fuzz=0', '--batch', '--forward', '-p1', '-i', str(PATCH)],
                               cwd=root / ('mesa-' + VERSION), check=True, env=clean_build_env())
            if args.variant in ('neon', 'neon-tile32'):
                format_source = root / ('mesa-' + VERSION) / 'src/mesa/main/format_utils.c'
                if digest(format_source) != FORMAT_SHA['baseline']:
                    raise RuntimeError('Pristine format_utils.c drifted')
                subprocess.run(['patch', '--fuzz=0', '--batch', '--forward', '-p1', '-i', str(NEON_PATCH)],
                               cwd=root / ('mesa-' + VERSION), check=True, env=clean_build_env())
                if digest(format_source) != FORMAT_SHA['neon']:
                    raise RuntimeError('NEON source output drifted')
            if args.variant == 'neon-tile32':
                tile_source = root / ('mesa-' + VERSION) / 'src/panfrost/shared/pan_tiling.c'
                if digest(tile_source) != TILE_SOURCE_SHA['input']:
                    raise RuntimeError('Pristine tiling source drifted')
                subprocess.run(['patch', '--fuzz=0', '--batch', '--forward', '-p1', '-i', str(TILE_PATCH)],
                               cwd=root / ('mesa-' + VERSION), check=True, env=clean_build_env())
                if digest(tile_source) != TILE_SOURCE_SHA['output']:
                    raise RuntimeError('Tiling patch output drifted')
            if digest(resource) != RESOURCE_SHA[args.variant]:
                raise RuntimeError('Diagnostic patch output does not match the reviewed source')
            receipt = {'inputs': expected, 'source_tree_sha256': tree_digest(root / ('mesa-' + VERSION)), 'phase': 'prepared'}
            save(path, receipt)
        else:
            receipt = json.loads(path.read_text())
            verify(root, receipt, expected)
        if args.action in ('configure', 'build'):
            if platform.system() != 'Linux' or platform.machine() not in ('aarch64', 'arm64'):
                raise RuntimeError('Build on native Linux ARM64; no implicit cross/container build')
            if not args.meson:
                p.error('Provide --meson pointing to the private Meson1.4.1 executable')
            toolchain = tools(args.meson)
            if 'toolchain' in receipt and receipt['toolchain'] != toolchain:
                raise RuntimeError('Toolchain drift; use a fresh work directory')
            receipt['toolchain'] = toolchain
            env = clean_build_env(); env['LLVM_CONFIG'] = toolchain['llvm-config-18']['path']
            build = root / 'build'
            if receipt['phase'] == 'prepared':
                if build.exists():
                    raise RuntimeError('Partial configure exists; preserve it and choose a new work directory')
                save(path, receipt)
                subprocess.run([toolchain['meson']['path'], 'setup', str(build), str(root / ('mesa-' + VERSION)),
                                '--prefix=' + str(root / 'unused-private-prefix')] + OPTIONS, check=True, env=env)
                receipt['phase'] = 'configured'; save(path, receipt)
            if args.action == 'build':
                subprocess.run([toolchain['meson']['path'], 'compile', '-C', str(build), '-j', str(args.jobs)], check=True, env=env)
                verify(root, receipt, expected)
                make_launcher(root, receipt)
                receipt['phase'] = 'built'; save(path, receipt)
        if args.action == 'verify' and receipt['phase'] == 'built':
            if any(digest(Path(name)) != sha for name, sha in receipt['outputs'].items()) or digest(root / 'launch.py') != receipt['launcher_sha256']:
                raise RuntimeError('Built output/launcher drifted')
            if any(not Path(name).is_symlink() or os.readlink(name) != target for name, target in receipt['runtime_links'].items()):
                raise RuntimeError('Built library link drifted')
        print(json.dumps({'variant': args.variant, 'phase': receipt['phase'], 'receipt': str(path),
                          'graphics_launched': False, 'system_install_performed': False}))


class ReceiptTests(unittest.TestCase):
    def test_source_mutation_and_symlink_escape_cannot_reuse_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); source = root / ('mesa-' + VERSION); source.mkdir()
            file = source / 'input.c'; file.write_text('original')
            receipt = {'inputs': {'pin': 'fixed'}, 'source_tree_sha256': tree_digest(source)}
            verify(root, receipt, {'pin': 'fixed'})
            file.write_text('changed')
            with self.assertRaises(RuntimeError): verify(root, receipt, {'pin': 'fixed'})
            file.unlink(); file.symlink_to('/etc/passwd')
            with self.assertRaises(RuntimeError): tree_digest(source)

    def test_changed_variant_or_patch_pin_cannot_reuse_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); (root / ('mesa-' + VERSION)).mkdir()
            receipt = {'inputs': {'variant': 'baseline'}, 'source_tree_sha256': tree_digest(root / ('mesa-' + VERSION))}
            with self.assertRaises(RuntimeError): verify(root, receipt, {'variant': 'patched'})


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))

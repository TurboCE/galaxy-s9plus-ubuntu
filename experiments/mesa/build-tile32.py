#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Rebuild a tiled-image candidate in a new copy; never install or restart UI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline-build', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
if os.geteuid() == 0 or platform.system() != 'Linux' or platform.machine() != 'aarch64':
    p.error('Use an ordinary user on native Linux ARM64')
base, out = a.baseline_build.resolve(), a.output.absolute()
if out.exists() or out.is_symlink() or out.is_relative_to(base) or base.is_relative_to(out):
    p.error('Preserve the original build and use a separate new directory')
here = Path(__file__).resolve().parent
pins = json.loads((here / 'TILE32_TRIAL.json').read_text())
sha = lambda x: hashlib.sha256(x.read_bytes()).hexdigest()
relative = Path('mesa-25.2.8/src/panfrost/shared/pan_tiling.c')
patch = here / '0003-panfrost-neon-tile32.patch'
assert sha(base / relative) == pins['input_sha256'] and sha(patch) == pins['patch_sha256']
targets = ['src/panfrost/shared/libpanfrost_shared.a.p/pan_tiling.c.o',
           'src/panfrost/shared/libpanfrost_shared.a',
           'src/gallium/targets/dri/libgallium-25.2.8.so']
commands = []
for target in targets:
    lines = subprocess.check_output(['ninja', '-C', str(base / 'build'), '-t', 'commands', target], text=True).splitlines()
    command = lines[-1]
    # Earlier isolated links pin these two read-only linker inputs absolutely.
    # Rebase only these reviewed paths into the copied source/build tree.
    for old, new in [(str(base / 'build/src/gallium/targets/dri/dri.sym'), 'src/gallium/targets/dri/dri.sym'),
                     (str(base / 'mesa-25.2.8/src/gallium/targets/dri/../dri.dyn'), '../mesa-25.2.8/src/gallium/targets/dri/../dri.dyn')]:
        command = command.replace(old, new)
    if str(base) in command or target not in command or '\n' in command:
        raise RuntimeError('Review a non-relative/unexpected generated build command')
    commands.append(command)
# The separately reviewed ordinary-user build system emits these shell commands;
# execute only the three final relative commands, not Meson regeneration against
# the preserved original build. Keep the complete private record for comparison.
shutil.copytree(base, out, symlinks=True)
os.chmod(out, 0o700)
subprocess.run(['patch', '--fuzz=0', '--batch', '-p1', '-d', str(out / 'mesa-25.2.8'), '-i', str(patch)], check=True)
assert sha(out / relative) == pins['output_sha256']
env = dict(os.environ)
for key in ['LD_PRELOAD', 'LD_AUDIT', 'LD_LIBRARY_PATH', 'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS']:
    env.pop(key, None)
for command in commands:
    subprocess.run(command, cwd=out / 'build', shell=True, check=True, env=env)
assert sha(base / relative) == pins['input_sha256']
record = {'commands': commands, 'patch': pins, 'source_sha256': sha(out / relative),
          'baseline_gallium_sha256': sha(base / 'build' / targets[-1]),
          'candidate_gallium_sha256': sha(out / 'build' / targets[-1]),
          'system_installed': False, 'desktop_restarted': False}
(out / 'tile32-rebuild.private.json').write_text(json.dumps(record, indent=2)+'\n')
(out / 'tile32-rebuild.private.json').chmod(0o600)
print('Tiled candidate built separately; no installation or display changes')

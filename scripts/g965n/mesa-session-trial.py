#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Explicit, timed per-user Mesa trial. Never called by build scripts."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import subprocess
import sys
import time
import tempfile

STATE = Path('/var/lib/g965n-mesa-trial')
VARIABLES = ('__EGL_VENDOR_LIBRARY_FILENAMES', '__EGL_VENDOR_LIBRARY_DIRS',
             'LD_LIBRARY_PATH', 'GBM_BACKENDS_PATH', 'LIBGL_DRIVERS_PATH',
             'PAN_MESA_DEBUG', 'MESA_SHADER_CACHE_DIR', 'MESA_SHADER_CACHE_DISABLE',
             'MESA_LOADER_DRIVER_OVERRIDE', 'GALLIUM_DRIVER', 'LIBGL_ALWAYS_SOFTWARE',
             'LD_PRELOAD', 'LD_AUDIT', 'DRI_PRIME', 'GBM_BACKEND', 'EGL_PLATFORM')
PARTITIONS = {'BOOT': 'sda10', 'DTB': 'sda8', 'DTBO': 'sda9', 'EFS': 'sda3',
              'CPEFS': 'sdd1', 'RADIO': 'sda12', 'MISC': 'sda15',
              'RECOVERY': 'sda11', 'PARAM': 'sda4'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def user_command(args):
    return ['runuser', '-u', 'ubuntu', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000',
            'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus', *args]


def manager(*args, **kwargs):
    return run(user_command(['systemctl', '--user', *args]), **kwargs)


def previous_environment(text):
    result = {}
    for line in text.splitlines():
        # show-environment uses shell quoting. Reject unsupported quoting rather
        # than silently losing a pre-existing value during restoration.
        if line.startswith(tuple(name + '=' for name in VARIABLES)):
            if '$\'' in line or '\n' in line or '\r' in line:
                raise RuntimeError('Unsupported previous GPU environment quoting')
            words = shlex.split(line)
            if len(words) != 1 or '=' not in words[0]:
                raise RuntimeError('Cannot preserve previous GPU environment')
            key, value = words[0].split('=', 1)
            result[key] = value
    return result


def validate_previous(previous):
    unknown = [key for key, value in previous.items()
               if value and not (key == 'PAN_MESA_DEBUG' and value == 'nocrc')]
    if unknown:
        raise RuntimeError('Pre-existing GPU override requires review: ' + ', '.join(unknown))


def write_state(directory, state):
    # Atomic replacement keeps the original restoration data intact if a write
    # fails, especially when accepting concurrently with the independent timer.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=directory, prefix='.state-', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, indent=2); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, directory / 'state.json')
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if temporary is not None and temporary.exists(): temporary.unlink()


def safe_new(path):
    if path.exists() or path.is_symlink():
        raise RuntimeError('Refuse existing trial path: ' + str(path))
    for parent in path.parents:
        if parent.is_symlink():
            raise RuntimeError('Symlink parent: ' + str(parent))


def verify_build(root):
    if not root.is_absolute() or not re.fullmatch(r'[A-Za-z0-9_./-]+', str(root)):
        raise RuntimeError('Build path must be an absolute simple path')
    receipt = json.loads((root / 'receipt.json').read_text())
    if receipt.get('phase') != 'built':
        raise RuntimeError('Build has not completed')
    outputs = receipt['outputs']
    required = ('libEGL_mesa.so.0.0.0', 'libgallium-25.2.8.so', 'libgbm.so.1.0.0', 'dri_gbm.so')
    for name in required:
        matches = [Path(p) for p in outputs if Path(p).name == name]
        if len(matches) != 1:
            raise RuntimeError('Missing coherent library: ' + name)
    for path, expected in outputs.items():
        p = Path(path)
        if not p.resolve().is_relative_to(root.resolve()) or digest(p) != expected:
            raise RuntimeError('Build output changed')
    for path, target in receipt['runtime_links'].items():
        p = Path(path)
        if not p.is_relative_to(root) or not p.resolve().is_relative_to(root.resolve()) or not p.is_symlink() or os.readlink(p) != target:
            raise RuntimeError('Build link changed')
    return receipt


def profile_files(home, trial, build, receipt):
    """Pure plan: never modify existing files or the immutable build receipt."""
    prefix = home / '.local/share' / ('g965n-mesa-trial-' + trial)
    vendor = prefix / 'vendor.json'
    wrapper = prefix / 'shell.py'
    dirs = [build / 'build' / p for p in ('src/egl', 'src/gallium/targets/dri', 'src/gbm')]
    environment = {'__EGL_VENDOR_LIBRARY_FILENAMES': str(vendor),
                   'LD_LIBRARY_PATH': ':'.join(map(str, dirs)),
                   'GBM_BACKENDS_PATH': str(build / 'build/src/gbm/backends/dri'),
                   'LIBGL_DRIVERS_PATH': str(build / 'build/src/gallium/targets/dri'),
                   'PAN_MESA_DEBUG': 'nocrc,noafbc',
                   'MESA_SHADER_CACHE_DIR': str(prefix / 'cache'),
                   'MESA_SHADER_CACHE_DISABLE': 'false'}
    egl = next(p for p in receipt['outputs'] if Path(p).name == 'libEGL_mesa.so.0.0.0')
    vendor_text = json.dumps({'file_format_version': '1.0.0', 'ICD': {'library_path': egl}}) + '\n'
    hashes = dict(receipt['outputs']); links = receipt['runtime_links']
    hashes[str(vendor)] = hashlib.sha256(vendor_text.encode()).hexdigest()
    code = '#!/usr/bin/python3\n# SPDX-License-Identifier: GPL-2.0-only\nimport os,hashlib\nfrom pathlib import Path\n'
    code += 'files=' + repr(hashes) + '\nlinks=' + repr(links) + '\nenvironment=' + repr(environment) + '\n'
    code += "for name,value in files.items():\n if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=value: raise SystemExit('Trial library changed')\n"
    code += 'build_root=' + repr(str(build.resolve())) + '\n'
    code += "for name,value in links.items():\n p=Path(name)\n if not p.resolve().is_relative_to(Path(build_root)) or not p.is_symlink() or os.readlink(name)!=value: raise SystemExit('Trial link changed')\n"
    code += 'env=dict(os.environ)\nfor name in ' + repr(VARIABLES) + ': env.pop(name,None)\nenv.update(environment)\n'
    code += "Path(environment['MESA_SHADER_CACHE_DIR']).mkdir(mode=0o700,parents=True,exist_ok=True)\nos.execve('/usr/bin/gnome-shell',['/usr/bin/gnome-shell'],env)\n"
    envfile = home / '.config/environment.d' / ('91-g965n-mesa-trial-' + trial + '.conf')
    dropin = home / '.config/systemd/user/org.gnome.Shell@wayland.service.d' / ('91-g965n-mesa-trial-' + trial + '.conf')
    # Normal app launches inherit the coherent environment. Only Shell uses the
    # hash-checking wrapper; no kernel, system graphics or greeter files change.
    envtext = ''.join(key + '=' + value + '\n' for key, value in environment.items())
    droptext = '[Service]\nExecStart=\nExecStart=/usr/bin/python3 ' + str(wrapper) + '\n'
    return {vendor: vendor_text, wrapper: code, envfile: envtext, dropin: droptext}, environment


def owned_cleanup(files):
    changed = []
    for name, expected in files.items():
        p = Path(name)
        if not p.exists() and not p.is_symlink():
            continue
        if any(parent.is_symlink() for parent in p.parents) or p.is_symlink() or not p.is_file() or digest(p) != expected:
            changed.append(name)
        else:
            p.unlink()
    return changed


def cleanup_user_files(files):
    # User-controlled path ancestors must never make root unlink a target.
    code = 'from pathlib import Path\nimport hashlib,json,sys\n'
    code += inspect.getsource(digest) + '\n' + inspect.getsource(owned_cleanup)
    code += '\nprint(json.dumps(owned_cleanup(json.loads(sys.argv[1]))))\n'
    return json.loads(run(user_command(['/usr/bin/python3', '-I', '-c', code,
                                       json.dumps(files)]), capture_output=True).stdout)


def write_user_files(files):
    # All profile creation runs as uid1000, including ancestor checks and mkdir.
    code = 'from pathlib import Path\nimport json,sys,os\n'
    code += inspect.getsource(safe_new)
    code += "\nos.umask(0o077)\nfor name,text in json.loads(sys.argv[1]).items():\n p=Path(name);safe_new(p);p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)\n with p.open('x') as f:f.write(text)\n p.chmod(0o700 if p.name=='shell.py' else 0o600)\n"
    run(user_command(['/usr/bin/python3', '-I', '-c', code,
                      json.dumps({str(p): text for p, text in files.items()})]))


def private_root(directory):
    return not directory.is_symlink() and directory.stat().st_uid == 0 and not directory.stat().st_mode & 0o077


def load_state(directory):
    if directory.parent != STATE or not private_root(directory):
        raise RuntimeError('Unsafe root rollback state')
    return json.loads((directory / 'state.json').read_text())


def restore_environment(previous):
    manager('unset-environment', *VARIABLES)
    if previous:
        manager('set-environment', *[key + '=' + value for key, value in previous.items()])
    manager('daemon-reload')


def shell_metadata(expected_prefix):
    text = manager('show', 'org.gnome.Shell@wayland.service', '-p', 'ActiveState',
                   '-p', 'MainPID', capture_output=True, timeout=5).stdout
    values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    try:
        pid = int(values.get('MainPID', '0'))
        if values.get('ActiveState') != 'active' or pid <= 0:
            return None
        process = Path('/proc') / str(pid)
        if process.stat().st_uid != 1000:
            return None
        paths = {line.split()[-1] for line in (process / 'maps').read_text().splitlines()
                 if any(name in line for name in ('libEGL_mesa', 'libgallium', 'libgbm'))}
        if not all(any(name in path for path in paths) for name in ('libEGL_mesa', 'libgallium', 'libgbm')):
            return None
        if not all(Path(path).is_relative_to(expected_prefix) for path in paths):
            return None
        return {'shell_pid': pid, 'shell_graphics_paths': sorted(paths)}
    except (OSError, ValueError):
        return None


def wait_stable_shell(expected_prefix, timeout=30):
    deadline = time.monotonic() + timeout
    last_pid, consecutive = None, 0
    while time.monotonic() < deadline:
        try: evidence = shell_metadata(expected_prefix)
        except (subprocess.SubprocessError, OSError): evidence = None
        if evidence:
            consecutive = consecutive + 1 if evidence['shell_pid'] == last_pid else 1
            last_pid = evidence['shell_pid']
            if consecutive >= 3:
                return dict(evidence, desktop_recovered=True)
        else:
            last_pid, consecutive = None, 0
        time.sleep(1)
    return {'desktop_recovered': False}


def clean_user_manager():
    # This ends ALL user-manager services. The root rollback job and tested SSH
    # scope are independent; arbitrary user background apps are not preserved.
    run(['systemctl', 'stop', 'gdm.service'], timeout=45)
    run(['systemctl', 'restart', 'user@1000.service'], timeout=45)


@contextmanager
def lifecycle_lock(directory):
    load_state(directory)
    with (directory / 'lifecycle.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def rollback(directory, automatic=False):
    with lifecycle_lock(directory):
        rollback_locked(directory, automatic)


def rollback_locked(directory, automatic=False):
    state = load_state(directory)
    if automatic and (state.get('accepted') or state.get('rollback_attempted')):
        return
    changed = cleanup_user_files(state['files'])
    state.update(rollback_attempted=True, rollback_preserved_changed_files=changed, files_restored=not changed,
                 environment_restored=False, desktop_recovered=False, rolled_back=False)
    write_state(directory, state)
    try:
        clean_user_manager()
        restore_environment(state['previous_environment'])
        state['environment_restored'] = True
        state['rolled_back'] = not changed
        write_state(directory, state)
        run(['systemctl', 'start', 'gdm.service'], timeout=45)
        state.update(wait_stable_shell(Path('/usr/lib')))
        write_state(directory, state)
    except BaseException:
        write_state(directory, state)
        raise
    if changed:
        raise RuntimeError('Rollback preserved modified files; manual review required: ' + ', '.join(changed))
    if not state['desktop_recovered']:
        raise RuntimeError('Files/environment restored but GNOME desktop did not recover; no restart retry performed')


def verify_device(args):
    if args.model != 'SM-G965N' or not args.consent_restart_desktop_trial:
        raise RuntimeError('Explicit G965N desktop restart trial consent required')
    spec = importlib.util.spec_from_file_location('deploy', Path(__file__).with_name('deploy-drivers.py'))
    deploy = importlib.util.module_from_spec(spec); spec.loader.exec_module(deploy)
    receipt = json.loads(args.kernel_receipt.read_text())
    if receipt.get('boot_sha256') != args.expected_boot_sha256:
        raise RuntimeError('Kernel receipt is not the explicitly selected BOOT')
    deploy.verify_kernel(receipt)
    manifest_bytes = args.backup_manifest.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != args.backup_manifest_sha256:
        raise RuntimeError('Backup manifest fingerprint mismatch')
    backup = json.loads(manifest_bytes)
    entries = {x['name']: x for x in backup.get('partitions', [])}
    if backup.get('model') != args.model or backup.get('complete') is not True or set(entries) != set(PARTITIONS) or len(backup.get('partitions', [])) != len(PARTITIONS):
        raise RuntimeError('Expected complete nine-partition backup manifest')
    if not all(type(e.get('bytes')) is int and e['bytes'] > 0 and re.fullmatch(r'[0-9a-f]{64}', e.get('sha256', '')) for e in entries.values()):
        raise RuntimeError('Invalid backup size/hash metadata')
    for name in ('EFS', 'CPEFS', 'RADIO'):
        device = Path('/dev') / PARTITIONS[name]
        label = subprocess.check_output(['lsblk', '-n', '-o', 'PARTLABEL', str(device)], text=True).strip()
        size = int(subprocess.check_output(['blockdev', '--getsize64', str(device)], text=True))
        if label != name or size != entries[name].get('bytes') or digest(device) != entries[name]['sha256']:
            raise RuntimeError('Backup is not for this unchanged handset')


def verify_shell_command():
    text = manager('show', 'org.gnome.Shell@wayland.service', '-p', 'ExecStart', '--value', capture_output=True).stdout
    if len(re.findall(r'path=/usr/bin/gnome-shell\s*;', text)) != 1 or not re.search(r'argv\[\]=/usr/bin/gnome-shell\s*;', text):
        raise RuntimeError('Shell command changed; review and preserve its exact arguments first')


@contextmanager
def reservation_lock():
    STATE.mkdir(mode=0o700, exist_ok=True)
    if not private_root(STATE):
        raise RuntimeError('Unsafe trial state root')
    with (STATE / '.reservation.lock').open('a') as stream:
        os.fchmod(stream.fileno(), 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def apply(args):
    verify_device(args)
    verify_shell_command()
    if pwd.getpwnam('ubuntu').pw_uid != 1000:
        raise RuntimeError('Expected ubuntu uid1000')
    trial = args.trial
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,35}', trial):
        raise RuntimeError('Use a short unique trial name')
    build = args.build.absolute(); receipt = verify_build(build)
    home = Path(pwd.getpwnam('ubuntu').pw_dir)
    files, environment = profile_files(home, trial, build, receipt)
    for path in files:
        safe_new(path)
    previous = previous_environment(manager('show-environment', capture_output=True).stdout)
    validate_previous(previous)
    # Scan, reserve state and arm its timer under one cross-trial lock.
    with reservation_lock():
        directory = STATE / trial; safe_new(directory)
        for previous_state in STATE.iterdir():
            if previous_state.name == '.reservation.lock':
                continue
            if not load_state(previous_state).get('rolled_back'):
                raise RuntimeError('Another staged or accepted profile must be rolled back first')
        directory.mkdir(mode=0o700)
        helper = directory / 'rollback.py'; shutil.copyfile(__file__, helper); helper.chmod(0o700)
        unit = 'g965n-mesa-rollback-' + trial
        state = {'files': {str(p): hashlib.sha256(text.encode()).hexdigest() for p, text in files.items()},
                 'previous_environment': previous, 'timer': unit, 'accepted': False,
                 'trial': trial, 'staged_at_unix': time.time(), 'boot_sha256': args.expected_boot_sha256}
        write_state(directory, state)
        (directory / 'state.json').chmod(0o600)
        # Reserve a system timer BEFORE the first user-file/environment write.
        run(['systemd-run', '--unit=' + unit, '--on-active=300s', '--timer-property=AccuracySec=1s',
             '/usr/bin/python3', str(helper), 'rollback', '--state', str(directory), '--automatic'])
        run(['systemctl', 'is-active', '--quiet', unit + '.timer'])
    try:
        write_user_files(files)
        clean_user_manager()
        restore_environment(environment)
        state['environment_applied'] = True
        write_state(directory, state)
        run(['systemctl', 'start', 'gdm.service'], timeout=45)
        state.update(wait_stable_shell(build.resolve()))
        write_state(directory, state)
        if not state['desktop_recovered']:
            raise RuntimeError('Trial GNOME Shell did not become stable; reverting once')
    except BaseException:
        rollback(directory)
        raise
    print('Trial Shell was stable for three observations. The original five-minute rollback timer remains armed.')
    print('Inspect actual SSH, Shell DSO maps and kernel health before explicit accept.')


def accept(args):
    with lifecycle_lock(args.state):
        accept_locked(args)


def accept_locked(args):
    state = load_state(args.state)
    evidence = json.loads(args.evidence.read_text())
    if evidence.get('trial') != state['trial'] or evidence.get('boot_sha256') != state['boot_sha256'] or evidence.get('captured_at_unix', 0) < state['staged_at_unix']:
        raise RuntimeError('Evidence does not describe this post-restart trial')
    if not all(evidence.get(key) is True for key in ('fresh_ssh', 'shell_private_dso_maps', 'kernel_health_reviewed')):
        raise RuntimeError('Actual post-restart evidence is required; source checks are insufficient')
    if state.get('rolled_back') or owned_cleanup_preview(state['files']):
        raise RuntimeError('Trial rolled back or owned files changed')
    # Explicit accept is the only path cancelling the independent root timer.
    run(['systemctl', 'stop', state['timer'] + '.timer'])
    if subprocess.run(['systemctl', 'is-active', '--quiet', state['timer'] + '.service']).returncode == 0:
        raise RuntimeError('Rollback already running; do not accept')
    state['accepted'] = True
    write_state(args.state, state)


def owned_cleanup_preview(files):
    return any(Path(p).is_symlink() or not Path(p).is_file() or digest(p) != sha for p, sha in files.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    stage = sub.add_parser('apply')
    stage.add_argument('--trial', required=True); stage.add_argument('--build', type=Path, required=True)
    stage.add_argument('--model', required=True)
    stage.add_argument('--kernel-receipt', type=Path, required=True)
    stage.add_argument('--expected-boot-sha256', required=True)
    stage.add_argument('--backup-manifest', type=Path, required=True)
    stage.add_argument('--backup-manifest-sha256', required=True)
    stage.add_argument('--consent-restart-desktop-trial', action='store_true')
    for name in ('rollback', 'accept'):
        p = sub.add_parser(name); p.add_argument('--state', type=Path, required=True)
        if name == 'accept': p.add_argument('--evidence', type=Path, required=True)
        else: p.add_argument('--automatic', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Root is required for the rollback timer and explicit lifecycle commands')
    os.umask(0o077)
    if args.action == 'apply': apply(args)
    elif args.action == 'rollback': rollback(args.state, args.automatic)
    else: accept(args)


if __name__ == '__main__':
    main()

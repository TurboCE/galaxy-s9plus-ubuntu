#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Timed physical-compositor experiment; preserves the accepted Mesa profile.

Creates a separate per-user Shell wrapper/drop-in, never replaces libraries or
changes the accepted parent profile files. An independent root timer restores
it unless explicit keep supplies real physical A/B and post-startup evidence.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import time

ROOT = Path('/var/lib/g965n-mesa-trial')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def protected(path, directory=False):
    info = path.lstat()
    require(not path.is_symlink() and info.st_uid == 0 and not info.st_mode & 0o077,
            'Expected root-private experiment state')
    require(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),
            'Unexpected state type')


def guard_device():
    base = Path('/var/lib/g965n-sensors')
    raw = (base / 'profile.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == (base / 'profile.sha256').read_text().split()[0],
            'Sensor profile changed')
    p = json.loads(raw)
    root = Path(p['kernel_receipt']['path']).parent
    guard = load(root / 'package/p2p-control-trial.py', 'physical_guard')
    receipt = guard.trusted_json(Path(p['kernel_receipt']['path']), p['kernel_receipt']['sha256'])
    backup = guard.trusted_json(Path(p['backup_manifest']['path']), p['backup_manifest']['sha256'])
    guard.validate(receipt, backup, require_off=False)
    require(receipt['kernel_version'].startswith('#48 '), 'Unqualified kernel')
    entries = {e['name']: e for e in backup['partitions']}
    for name, node in {'RECOVERY':'sda11', 'EFS':'sda3', 'CPEFS':'sdd1', 'RADIO':'sda12'}.items():
        value = subprocess.check_output(['sha256sum', '/dev/' + node], text=True).split()[0]
        require(value == entries[name]['sha256'], 'Protected backup changed: ' + name)
    return receipt['boot_sha256']


def helper_from_state(directory, state):
    path = directory / 'base-helper.py'
    protected(path)
    require(sha(path) == state['helper_sha256'], 'Rollback helper changed')
    return load(path, 'physical_base')


def restore(directory, automatic=False):
    protected(directory, directory=True)
    protected(directory / 'state.json')
    with (directory / 'lifecycle.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads((directory / 'state.json').read_text())
        if state.get('rolled_back') or (automatic and state.get('accepted')):
            return
        helper = helper_from_state(directory, state)
        changed = helper.cleanup_user_files(state['files'])
        require(not changed, 'Owned trial files were changed; preserved for review')
        helper.clean_user_manager()
        helper.manager('daemon-reload')
        subprocess.run(['systemctl', 'start', 'gdm.service'], check=True, timeout=45)
        evidence = helper.wait_stable_shell(Path(state['baseline_build']), timeout=40)
        require(evidence['desktop_recovered'], 'Original compositor not yet recovered; keep SSH and state')
        state.update(rolled_back=True, restore_evidence=evidence)
        helper.write_state(directory, state)
        subprocess.run(['systemctl', 'stop', state['timer'] + '.timer'], check=False,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print('Physical trial removed; accepted compositor library mapping restored')


def apply(args):
    boot = guard_device()
    require(pwd.getpwnam('ubuntu').pw_uid == 1000, 'Expected selected desktop user')
    protected(args.helper)
    require(sha(args.helper) == args.helper_sha256, 'Unreviewed experiment helper')
    helper = load(args.helper, 'source_base')
    unlocked = subprocess.check_output(helper.user_command([
        'gdbus', 'call', '--session', '--dest', 'org.gnome.ScreenSaver',
        '--object-path', '/org/gnome/ScreenSaver', '--method',
        'org.gnome.ScreenSaver.GetActive']), text=True, timeout=8).strip()
    require(unlocked == '(false,)', 'Locked desktop preserved; trial refused')
    baseline = args.baseline_build.resolve()
    candidate = args.candidate_build.resolve()
    require(baseline != candidate, 'Distinct build copies required')
    original = helper.verify_build(baseline)
    accepted = helper.load_state(args.accepted_state)
    require(accepted.get('accepted') and not accepted.get('rolled_back'), 'No accepted baseline')
    for name, expected in accepted['files'].items():
        require(sha(Path(name)) == expected, 'Accepted profile changed; no replacement attempted')
    evidence = helper.wait_stable_shell(baseline)
    require(evidence['desktop_recovered'], 'Baseline compositor not stable')
    clone = {'phase': 'built', 'outputs': {}, 'runtime_links': {}}
    for path, expected in original['outputs'].items():
        old = Path(path)
        new = candidate / old.relative_to(baseline)
        if old.name == 'libgallium-25.2.8.so':
            require(expected == args.baseline_gallium_sha256, 'Unexpected accepted Gallium')
            expected = args.candidate_gallium_sha256
        require(sha(new) == expected, 'Clone differs beyond the pinned Gallium candidate')
        require(new.resolve().is_relative_to(candidate), 'Escaping clone library')
        clone['outputs'][str(new)] = expected
    for path, target in original['runtime_links'].items():
        new = candidate / Path(path).relative_to(baseline)
        require(new.is_symlink() and os.readlink(new) == target and
                new.resolve().is_relative_to(candidate), 'Clone runtime link changed')
        clone['runtime_links'][str(new)] = target
    planned, environment = helper.profile_files(Path('/home/ubuntu'), args.state.name, candidate, clone)
    files = {p: text for p, text in planned.items() if p.name in ('vendor.json', 'shell.py')}
    text = next(v for p, v in planned.items() if '.service.d' in str(p))
    dropin = Path('/home/ubuntu/.config/systemd/user/org.gnome.Shell@wayland.service.d') / (
        '99-g965n-' + args.state.name + '.conf')
    files[dropin] = text
    for p in files:
        helper.safe_new(p)
    with helper.reservation_lock():
        for previous in ROOT.glob('physical-*'):
            protected(previous, directory=True)
            protected(previous / 'state.json')
            require(json.loads((previous / 'state.json').read_text()).get('rolled_back'),
                    'Another physical experiment is active')
        require(not args.state.exists(), 'Existing experiment state preserved')
        args.state.mkdir(mode=0o700)
        shutil.copyfile(args.helper, args.state / 'base-helper.py')
        (args.state / 'base-helper.py').chmod(0o600)
        shutil.copyfile(__file__, args.state / 'session.py')
        (args.state / 'session.py').chmod(0o600)
        state = {'files': {str(p): hashlib.sha256(v.encode()).hexdigest() for p, v in files.items()},
                 'baseline_build': str(baseline), 'candidate_build': str(candidate),
                 'helper_sha256': args.helper_sha256, 'accepted': False, 'rolled_back': False,
                 'timer': 'g965n-' + args.state.name + '-restore', 'baseline_evidence': evidence,
                 'candidate_environment': environment, 'boot_sha256': boot,
                 'staged_at_unix': time.time(), 'scope': 'gnome-shell-overlay',
                 'parent_state': str(args.accepted_state),
                 'parent_state_sha256': sha(args.accepted_state / 'state.json'),
                 'parent_files': dict(accepted['files']),
                 'candidate_gallium_sha256': args.candidate_gallium_sha256}
        helper.write_state(args.state, state)
        subprocess.run(['systemd-run', '--quiet', '--unit=' + state['timer'], '--on-active=240s',
                        '--timer-property=AccuracySec=1s', '/usr/bin/python3',
                        str(args.state / 'session.py'), 'restore', '--state', str(args.state),
                        '--automatic'], check=True)
        subprocess.run(['systemctl', 'is-active', '--quiet', state['timer'] + '.timer'], check=True)
    try:
        helper.write_user_files(files)
        helper.clean_user_manager()
        helper.manager('daemon-reload')
        subprocess.run(['systemctl', 'start', 'gdm.service'], check=True, timeout=45)
        result = helper.wait_stable_shell(candidate, timeout=40)
        require(result['desktop_recovered'], 'Candidate compositor not stable')
        state['candidate_evidence'] = result
        helper.write_state(args.state, state)
        print('Physical candidate compositor stable; independent four-minute restoration armed')
    except BaseException:
        restore(args.state)
        raise


def keep(args):
    protected(args.state, directory=True)
    protected(args.state / 'state.json')
    protected(args.evidence)
    with (args.state / 'lifecycle.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads((args.state / 'state.json').read_text())
        require(not state.get('rolled_back') and state.get('scope') == 'gnome-shell-overlay',
                'Trial already restored or wrong scope')
        require(guard_device() == state['boot_sha256'], 'BOOT changed during graphics trial')
        proof = json.loads(args.evidence.read_text())
        require(proof.get('trial') == args.state.name and
                proof.get('boot_sha256') == state['boot_sha256'] and
                proof.get('gallium_sha256') == state['candidate_gallium_sha256'] and
                proof.get('captured_at_unix', 0) >= state['staged_at_unix'],
                'Evidence does not describe this post-startup library/BOOT')
        require(all(proof.get(k) is True for k in ('fresh_ssh', 'shell_private_dso_maps',
                'kernel_health_reviewed', 'physical_ab_comparison', 'texture_readback')),
                'Physical comparison, pixel check and post-startup hardware evidence required')
        helper = helper_from_state(args.state, state)
        require(not helper.owned_cleanup_preview(state['files']), 'Trial files changed')
        parent = Path(state['parent_state'])
        require(sha(parent / 'state.json') == state['parent_state_sha256'] and
                all(sha(Path(n)) == h for n, h in state['parent_files'].items()),
                'Accepted parent changed; do not keep this overlay')
        result = helper.wait_stable_shell(Path(state['candidate_build']))
        require(result['desktop_recovered'], 'Actual candidate compositor is not stable')
        subprocess.run(['systemctl', 'stop', state['timer'] + '.timer'], check=True)
        # Under the same lifecycle lock, any automatic restore can only be
        # waiting before changes. Stop it, then publish the accepted flag.
        subprocess.run(['systemctl', 'stop', state['timer'] + '.service'], check=False,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        state.update(accepted=True, keep_evidence=proof, keep_mapping=result)
        helper.write_state(args.state, state)
        print('Verified Shell overlay kept; original parent profile remains the manual fallback')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    stage = sub.add_parser('apply')
    for name in ('helper', 'accepted-state', 'baseline-build', 'candidate-build'):
        stage.add_argument('--' + name, type=Path, required=True)
    for name in ('helper-sha256', 'baseline-gallium-sha256', 'candidate-gallium-sha256'):
        stage.add_argument('--' + name, required=True)
    stage.add_argument('--confirm-sm-g965n-backed-up-desktop-restart', action='store_true', required=True)
    rollback = sub.add_parser('restore')
    rollback.add_argument('--automatic', action='store_true')
    retain = sub.add_parser('keep')
    retain.add_argument('--evidence', type=Path, required=True)
    retain.add_argument('--confirm-sm-g965n-verified-shell-overlay', action='store_true', required=True)
    for command in (stage, rollback, retain):
        command.add_argument('--state', type=Path, required=True)
    args = p.parse_args()
    require(os.geteuid() == 0, 'Root required')
    os.umask(0o077)
    require(args.state.parent == ROOT and re.fullmatch('physical-[a-z0-9-]{1,25}', args.state.name),
            'Expected a new direct physical-trial state directory')
    if args.action == 'apply':
        for key in ('helper_sha256', 'baseline_gallium_sha256', 'candidate_gallium_sha256'):
            require(re.fullmatch('[a-f0-9]{64}', getattr(args, key)), 'Invalid source/library pin')
        apply(args)
    elif args.action == 'keep':
        keep(args)
    else:
        restore(args.state, automatic=args.automatic)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare private volatile magnetic init inputs from verified OWN backups.

Offline only: no handset access, mounts, flashing, firmware publication or
original EFS writes. Register/layout facts follow Samsung Electronics' GPLv2
magnetic_common.c and ssp_dev.c in LineageOS exynos9810 commit
6a9461f9460ca51d1217e5069a5d5556fcc79e63 (Copyright Samsung Electronics).
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verified_backup(path, name):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file() or path.name != name + '.img':
        raise ValueError('Expected an ordinary named partition backup')
    manifest = json.loads(path.with_name('manifest.json').read_bytes())
    if (manifest.get('complete') is not True or manifest.get('model') != 'SM-G965N' or
            not manifest.get('bootloader', '').startswith('G965N')):
        raise ValueError('Expected complete own G965N backup manifest')
    entries = [e for e in manifest['partitions'] if e.get('name') == name]
    if len(entries) != 1:
        raise ValueError('Missing or ambiguous partition receipt')
    sha = digest(path)
    if entries[0].get('sha256') != sha or entries[0].get('bytes') != path.stat().st_size:
        raise ValueError('Partition backup differs from receipt')
    return path, sha


def prepare(stock_boot, efs_backup, docker_image=None):
    boot, boot_sha = verified_backup(stock_boot, 'BOOT')
    efs, efs_sha = verified_backup(efs_backup, 'EFS')
    spec = importlib.util.spec_from_file_location('magnetic_stock_tree', ROOT/'experiments/modem/verify-overlay.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tree = module.stock_tree(boot, 26)
    if tree[''].get('model_info-hw_rev') != struct.pack('>I', 26):
        raise ValueError('Expected actual stock revision26 tree')
    candidates = [p for p in tree.values() if 'ssp-mag-array' in p]
    if len(candidates) != 1:
        raise ValueError('Missing or ambiguous stock magnetic board data')
    props = candidates[0]
    if any(props.get(k) != struct.pack('>I', v) for k, v in {
            'ssp-mag-type': 1, 'ssp-mag-position': 5, 'ssp-acc-position': 7}.items()):
        raise ValueError('Stock magnetic sensor configuration differs')
    pdc = props['ssp-mag-array']
    if len(pdc) != 27 or not any(pdc):
        raise ValueError('Missing actual AKM PDC matrix')
    command = ['debugfs', '-R', 'cat /FactoryApp/gyro_cal_data', str(efs)]
    if docker_image:
        if ':' in str(efs) or not docker_image or docker_image.startswith('-'):
            raise ValueError('Unsafe container bind/image input')
        command = ['docker', 'run', '--rm', '--network', 'none',
                   '-v', str(efs) + ':/input/efs.img:ro', docker_image,
                   'debugfs', '-R', 'cat /FactoryApp/gyro_cal_data', '/input/efs.img']
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            check=True, timeout=60)
    # Stock gyro occupies12bytes, followed by exactly13bytes of AKM state.
    if len(result.stdout) != 25:
        raise ValueError('Actual gyro/magnetic NVM record is not25bytes')
    calibration = result.stdout[12:]
    if not any(calibration) or all(x == 255 for x in calibration):
        raise ValueError('No usable own magnetic calibration; do not fabricate it')
    return {'schema': 1, 'model': 'SM-G965N', 'revision': 26, 'mag_type': 1,
            'stock_mag_position': 5, 'position_command_sent': False,
            'pdc': list(pdc), 'mag_calibration': list(calibration),
            'own_stock_boot_sha256': boot_sha, 'own_efs_backup_sha256': efs_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-boot', type=Path, required=True)
    parser.add_argument('--efs-backup', type=Path, required=True)
    parser.add_argument('--docker-image', help='Optional local Linux image containing debugfs')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = prepare(args.stock_boot, args.efs_backup, args.docker_image)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print('Prepared private magnetic init input; no handset writes; keep output out of Git.')


if __name__ == '__main__':
    main()

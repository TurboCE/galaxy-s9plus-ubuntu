#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stage opt-in audio/Bluetooth startup on the handset, guarded by exact BOOT.

Does not flash, load modules immediately, enable modem/sensors, or install
firmware. --stage-for-next-boot permits staging for a different kernel; every
service still verifies the actual running kernel and BOOT before driver load.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import re

FILES = {'audio': 'snd-zrn-abox.ko', 'bluetooth': 'zrn-bt.ko'}


def validate_receipt(receipt):
    if receipt.get('model') != 'SM-G965N' or not re.fullmatch(r'[0-9a-f]{64}', receipt.get('boot_sha256', '')):
        raise RuntimeError('Invalid model/BOOT receipt')
    if type(receipt.get('boot_bytes')) is not int or not 0 < receipt['boot_bytes'] <= 57671680:
        raise RuntimeError('Invalid BOOT size')


def verify_kernel(receipt):
    validate_receipt(receipt)
    if b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise RuntimeError('Wrong board')
    if os.uname().release != receipt['kernel_release'] or os.uname().version != receipt['kernel_version']:
        raise RuntimeError('Kernel does not match the tested module package')
    count = receipt['boot_bytes']
    if receipt['model'] != 'SM-G965N' or not 0 < count <= 57671680:
        raise RuntimeError('Unexpected model/BOOT size')
    label = subprocess.check_output(['lsblk', '-n', '-o', 'PARTLABEL', '/dev/sda10'], text=True).strip()
    if label != 'BOOT':
        raise RuntimeError('Unexpected BOOT mapping')
    with open('/dev/sda10', 'rb') as stream:
        if hashlib.sha256(stream.read(count)).hexdigest() != receipt['boot_sha256']:
            raise RuntimeError('Actual BOOT does not match package; no driver loaded')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--enable-audio', action='store_true')
    parser.add_argument('--enable-bluetooth', action='store_true')
    parser.add_argument('--stage-for-next-boot', action='store_true')
    parser.add_argument('--verify', type=Path, help='Service-only receipt check')
    parser.add_argument('--feature', choices=FILES)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run as root on the handset')
    if args.verify:
        receipt = json.loads(args.verify.read_text())
        verify_kernel(receipt)
        if not args.feature:
            raise RuntimeError('Expected service feature')
        module = args.verify.parent / FILES[args.feature]
        if hashlib.sha256(module.read_bytes()).hexdigest() != receipt['modules'][args.feature]['sha256']:
            raise RuntimeError('Installed module changed; no driver loaded')
        return
    if not args.package or not (args.enable_audio or args.enable_bluetooth):
        raise SystemExit('Select a package and explicit audio/Bluetooth enable flags')
    receipt = json.loads((args.package / 'manifest.json').read_text())
    validate_receipt(receipt)
    if receipt['model'] != 'SM-G965N' or b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        raise SystemExit('Expected G965N package on star2lte')
    if not args.stage_for_next_boot:
        verify_kernel(receipt)
    selected = [f for f, enable in [('audio', args.enable_audio), ('bluetooth', args.enable_bluetooth)] if enable]
    required = {'audio': ['calliope_sram.bin', 'calliope_dram.bin', 'calliope_iva.bin'],
                'bluetooth': ['brcm/BCM.samsung,star2lte.hcd']}
    sources = {}
    for feature in selected:
        if feature == 'bluetooth' and receipt.get('built_in_aes') is not True:
            raise RuntimeError('Bluetooth startup requires a kernel with built-in AES')
        entry = receipt['modules'][feature]
        if entry['path'] != feature + '/' + FILES[feature]:
            raise RuntimeError('Unexpected module path')
        source = (args.package / entry['path']).resolve()
        if not source.is_relative_to(args.package.resolve()) or not source.is_file():
            raise RuntimeError('Unsafe/missing package module')
        data = source.read_bytes()
        if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise RuntimeError('Module checksum mismatch')
        for firmware in required[feature]:
            if not (Path('/lib/firmware') / firmware).is_file() or (Path('/lib/firmware') / firmware).stat().st_size == 0:
                raise RuntimeError('Supply own-device firmware first: ' + firmware)
        sources[feature] = source
    os.umask(0o022)
    destination = Path('/usr/lib/g965n-experiments') / receipt['boot_sha256'][:16]
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')
    shutil.copyfile(__file__, destination / 'verify.py')
    for feature in selected:
        verify = f'/usr/bin/python3 {destination}/verify.py --verify {destination}/manifest.json --feature {feature}'
        module = destination / sources[feature].name
        shutil.copyfile(sources[feature], module)
        if feature == 'audio':
            service = f'''[Unit]
Description=Experimental G965N speaker and microphone driver
After=local-fs.target
Before=display-manager.service
[Service]
Type=oneshot
ExecStartPre={verify}
ExecStart=/usr/sbin/insmod {module} enable_g965n=1 capture=1 cp_vss=0 mic_gain=40
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
'''
        else:
            service = f'''[Unit]
Description=Experimental G965N Bluetooth controller
After=local-fs.target
Before=bluetooth.service
Wants=bluetooth.service
[Service]
Type=simple
ExecStartPre={verify}
ExecStartPre=/usr/sbin/insmod {module} enable_g965n=1
ExecStart=/usr/bin/btattach -B /dev/ttySAC0 -P bcm -S 115200
Restart=no
[Install]
WantedBy=multi-user.target
'''
        Path('/etc/systemd/system/g965n-' + feature + '.service').write_text(service)
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable'] + ['g965n-' + f + '.service' for f in selected], check=True)
    print('Startup staged for selected drivers; nothing loaded now. Verify after reboot.')


if __name__ == '__main__':
    main()

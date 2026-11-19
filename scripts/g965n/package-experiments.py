#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only receipt for opt-in modules and their exact kernel/BOOT artifact."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

FILES = {'audio': 'snd-zrn-abox.ko', 'bluetooth': 'zrn-bt.ko',
         'sensors': 'zrn-bbd.ko', 'modem': 'g965n-modem.ko',
         'iio-bridge': 'g965n-iio-bridge.ko'}
ROOT = Path(__file__).resolve().parents[2]
OVERLAY_SOURCE = 'experiments/modem/g965n-modem-overlay.dts'


def modem_overlay(output, stock_boot=None):
    """Describe the built GPL overlay; stock comparison is a separate qualification."""
    relative = 'modem/modem.dtbo'
    data = (output / relative).read_bytes()
    if not 40 <= len(data) <= 128 * 1024:
        raise ValueError('Modem overlay is outside the reviewed driver size limit')
    verifier = ROOT / 'experiments/modem/verify-overlay.py'
    spec = importlib.util.spec_from_file_location('g965n_overlay_verifier', verifier)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    nodes = module.tree(data)
    if nodes.get('/fragment@0', {}).get('target-path') != b'/\0':
        raise ValueError('Modem overlay must target the root node')
    prefix = '/fragment@0/__overlay__/'
    if any(prefix + name not in nodes for name in module.NODES):
        raise ValueError('Modem overlay is missing a required hardware node')
    if nodes[prefix + 'mif_pdata'].get('samsung,hw-revision') != struct.pack('>I', 26):
        raise ValueError('Modem overlay revision does not match the tracked G965N source')
    qualification = {'status': 'not-performed', 'revision': 26,
                     'scope': 'No owner stock BOOT comparison; hardware probing remains unqualified'}
    if stock_boot is not None:
        subprocess.run([sys.executable, str(verifier), str(stock_boot),
                        str(output / relative), '--revision', '26'], check=True)
        qualification = {'status': 'passed', 'revision': 26,
                         'scope': 'Stock hardware properties only; not device boot or modem operation'}
    source = (ROOT / OVERLAY_SOURCE).read_bytes()
    return {'path': relative, 'firmware_request': 'g965n/modem.dtbo',
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'source': {'path': OVERLAY_SOURCE, 'sha256': hashlib.sha256(source).hexdigest(),
                       'license': 'GPL-2.0-only', 'upstream': 'LineageOS/android_kernel_samsung_exynos9810',
                       'commit': '6a9461f9460ca51d1217e5069a5d5556fcc79e63',
                       'path_upstream': 'arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts'},
            'stock_verification': qualification}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel-out', type=Path, required=True)
    p.add_argument('--boot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--features', nargs='+', choices=FILES, required=True)
    p.add_argument('--stock-boot', type=Path,
                   help='Optional private original BOOT for modem overlay property comparison')
    a = p.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', a.source_commit):
        raise SystemExit('Provide the actual host source commit')
    version = re.search(r'^#define UTS_VERSION "([^"]+)"$',
        (a.kernel_out / 'include/generated/utsversion.h').read_text(), re.M)
    if not version:
        raise SystemExit('Kernel version header missing')
    modules = {}
    for feature in a.features:
        relative = feature + '/' + FILES[feature]
        data = (a.output / relative).read_bytes()
        modules[feature] = {'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    boot = a.boot.read_bytes()
    if boot[:8] != b'ANDROID!' or not 0 < len(boot) <= 57671680:
        raise SystemExit('Invalid G965N BOOT artifact')
    built_in_iio = 'CONFIG_IIO=y' in (a.kernel_out / '.config').read_text().splitlines()
    if 'iio-bridge' in a.features and not built_in_iio:
        raise SystemExit('IIO bridge requires the exact kernel built-in IIO core')
    receipt = {'model': 'SM-G965N', 'kernel_release': (a.kernel_out / 'include/config/kernel.release').read_text().strip(),
               'kernel_version': version[1], 'source_commit': a.source_commit,
               'boot_bytes': len(boot), 'boot_sha256': hashlib.sha256(boot).hexdigest(),
               'built_in_aes': 'CONFIG_CRYPTO_AES=y' in (a.kernel_out / '.config').read_text().splitlines(),
               'built_in_iio': built_in_iio, 'modules': modules}
    if 'modem' in a.features:
        receipt['artifacts'] = {'modem_overlay': modem_overlay(a.output, a.stock_boot)}
    (a.output / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Module receipt written; no device access or deployment.')


if __name__ == '__main__':
    main()

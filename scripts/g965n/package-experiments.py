#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build-only receipt for opt-in modules and their exact kernel/BOOT artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import re

FILES = {'audio': 'snd-zrn-abox.ko', 'bluetooth': 'zrn-bt.ko',
         'sensors': 'zrn-bbd.ko', 'modem': 'g965n-modem.ko'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel-out', type=Path, required=True)
    p.add_argument('--boot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--features', nargs='+', choices=FILES, required=True)
    a = p.parse_args()
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
    receipt = {'model': 'SM-G965N', 'kernel_release': (a.kernel_out / 'include/config/kernel.release').read_text().strip(),
               'kernel_version': version[1], 'source_commit': a.source_commit,
               'boot_bytes': len(boot), 'boot_sha256': hashlib.sha256(boot).hexdigest(),
               'built_in_aes': 'CONFIG_CRYPTO_AES=y' in (a.kernel_out / '.config').read_text().splitlines(),
               'modules': modules}
    (a.output / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Module receipt written; no device access or deployment.')


if __name__ == '__main__':
    main()

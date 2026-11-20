#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Cache own-config Broadcom LTO assistance over verified HTTPS; no positions."""
import email.utils
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import urllib.parse
import urllib.request

CONFIG = Path('/run/g965n-sensor-runtime/root/system/etc/gps_psds.conf')
CACHE = Path('/var/lib/g965n-gnss-assistance')
LIMIT = 512 * 1024
TTL = 24 * 3600
VALIDITY = 4 * 24 * 3600


def sources(raw):
    result = []
    for line in raw.decode('utf-8').splitlines():
        match = re.fullmatch(r'\s*XTRA_SERVER_[123]\s*=\s*(\S+)\s*', line)
        if not match:
            continue
        url = urllib.parse.urlsplit(match[1])
        if (url.scheme not in ('http', 'https') or
                url.netloc not in ('gllto1.glpals.com', 'gllto2.glpals.com', 'gllto3.glpals.com') or
                url.path != '/4day/v5/latest/lto2.dat' or url.query or url.fragment):
            raise RuntimeError('Unqualified Broadcom assistance source')
        result.append(urllib.parse.urlunsplit(('https', url.netloc, url.path, '', '')))
    if not result:
        raise RuntimeError('No qualified own-device LTO source')
    return result


def valid_metadata(metadata, data, config, now):
    return (isinstance(metadata, dict) and
            metadata.get('config_sha256') == hashlib.sha256(config).hexdigest() and
            metadata.get('source') in sources(config) and
            metadata.get('sha256') == hashlib.sha256(data).hexdigest() and
            512 < len(data) <= LIMIT and
            0 <= now - metadata.get('downloaded_at', 0) < TTL and
            0 <= now - metadata.get('modified_at', 0) < VALIDITY)


def read_cache():
    try:
        for path in (CACHE, CACHE / 'metadata.json', CACHE / 'lto.dat'):
            info = path.lstat()
            if info.st_uid != 0 or info.st_mode & 0o077 or stat.S_ISLNK(info.st_mode):
                raise RuntimeError('Assistance cache ownership or permissions changed')
            if path.name == 'lto.dat' and info.st_size > LIMIT:
                raise RuntimeError('Assistance cache exceeds size limit')
            if path.name == 'metadata.json' and info.st_size > 16384:
                raise RuntimeError('Assistance metadata exceeds size limit')
        raw = CONFIG.read_bytes()
        data = (CACHE / 'lto.dat').read_bytes()
        metadata = json.loads((CACHE / 'metadata.json').read_text())
        if valid_metadata(metadata, data, raw, time.time()):
            return data
    except (OSError, ValueError, TypeError, RuntimeError):
        pass
    return None


def fetch():
    if os.geteuid() != 0:
        raise RuntimeError('Cache preparation requires the authorized system account')
    config = CONFIG.read_bytes()
    if read_cache() is not None:
        print('GNSS assistance cache is fresh')
        return
    CACHE.mkdir(mode=0o700, exist_ok=True)
    info = CACHE.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        raise RuntimeError('Unexpected assistance cache directory')
    for url in sources(config):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'G965N-GNSS-Diagnostic/1'})
            with urllib.request.urlopen(request, timeout=12) as response:
                if response.status != 200 or urllib.parse.urlsplit(response.url).scheme != 'https':
                    raise RuntimeError('Unexpected assistance response')
                modified = email.utils.parsedate_to_datetime(response.headers['Last-Modified']).timestamp()
                data = response.read(LIMIT + 1)
                if 'html' in response.headers.get('Content-Type', '').lower():
                    raise RuntimeError('Assistance endpoint returned a web page')
            now = time.time()
            metadata = {'source': url, 'downloaded_at': now, 'modified_at': modified,
                        'config_sha256': hashlib.sha256(config).hexdigest(),
                        'sha256': hashlib.sha256(data).hexdigest()}
            if not valid_metadata(metadata, data, config, now):
                raise RuntimeError('Assistance freshness or integrity check failed')
            for name, content in [('lto.dat', data), ('metadata.json', (json.dumps(metadata) + '\n').encode())]:
                with tempfile.NamedTemporaryFile(dir=CACHE, prefix=name + '.', delete=False) as stream:
                    temporary = Path(stream.name)
                    try:
                        stream.write(content)
                        stream.flush()
                        os.fsync(stream.fileno())
                        temporary.replace(CACHE / name)
                    finally:
                        temporary.unlink(missing_ok=True)
            print('GNSS assistance downloaded, freshness checked and privately cached')
            return
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            continue
    raise RuntimeError('Configured HTTPS assistance sources unavailable or unqualified')


if __name__ == '__main__':
    try:
        fetch()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print('GNSS assistance refresh unavailable; standalone remains available (' + type(error).__name__ + ')')
        raise SystemExit(2)

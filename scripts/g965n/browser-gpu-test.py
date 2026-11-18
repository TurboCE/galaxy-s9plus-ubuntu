#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Serve the local WebGL check on loopback and save its private result; no settings change."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise SystemExit('Use a new private result path')
    page = Path(__file__).with_name('gpu-webgl.html').read_bytes()
    result = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path != '/':
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(page)))
            self.end_headers(); self.wfile.write(page)

        def do_POST(self):
            nonlocal result
            if self.path != '/result' or not 0 < int(self.headers.get('Content-Length', '0')) <= 8192:
                self.send_error(400); return
            try:
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if not isinstance(data, dict):
                    raise ValueError('Expected result object')
            except (ValueError, UnicodeError):
                self.send_error(400); return
            result = data
            self.send_response(204); self.end_headers()

    with HTTPServer(('127.0.0.1', 8765), Handler) as server:
        server.timeout = 1
        deadline = time.monotonic() + 90
        print('Open http://127.0.0.1:8765/ on the handset. Waiting at most90seconds.', flush=True)
        while result is None and time.monotonic() < deadline:
            server.handle_request()
    if result is None:
        result = {'passed': False, 'error': 'Browser result timeout'}
    os.umask(0o077)
    a.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    raise SystemExit(0 if result.get('passed') is True else 2)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded visible Firefox WebGL test with a throwaway WebDriver profile.

No GPU-force/sandbox preferences, personal profiles, firmware or partition I/O.
Use a separately verified Mozilla geckodriver binary. Raw logs stay private.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import subprocess
import tempfile
import threading
import time
from urllib.request import ProxyHandler, Request, build_opener


def policy_unforced(policy):
    for entries in policy.values():
        if any(entries.get(key) is True for key in ('webgl.force-enabled', 'layers.acceleration.force-enabled')):
            return False
        if any(key.startswith('security.sandbox.') and
               (key.endswith('.level') and type(value) is int and value == 0)
               for key, value in entries.items()):
            return False
    return True


def qualified(report, page, capabilities, policy):
    return (all(type(report.get(k)) is int for k in ('frames', 'mismatches', 'compared_bytes')) and
            isinstance(report.get('renderer'), str) and
            report.get('passed') is True and report.get('frames') == 120 and
            report.get('mismatches') == 0 and report.get('context_lost') is False and
            report.get('compared_bytes') == 120 * 256 * 256 * 4 and
            bool(re.search('Mali', report.get('renderer', ''), re.I)) and
            not re.search('llvmpipe|softpipe|SwiftShader', report.get('renderer', ''), re.I) and
            page.get('visible') is True and page.get('focused') is True and
            capabilities.get('moz:headless') is False and policy_unforced(policy))


def request(base, method, path, data=None, timeout=40):
    payload = None if data is None else json.dumps(data).encode()
    req = Request(base + path, data=payload, method=method,
                  headers={'Content-Type': 'application/json'})
    # Local test control must never follow the caller's HTTP proxy settings.
    with build_opener(ProxyHandler({})).open(req, timeout=timeout) as response:
        result = json.load(response)
    if isinstance(result.get('value'), dict) and result['value'].get('error'):
        raise RuntimeError('WebDriver operation failed: ' + result['value']['error'])
    return result['value']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=['SM-G965N'], required=True)
    parser.add_argument('--consent-browser-trial', action='store_true')
    parser.add_argument('--geckodriver', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cadence', action='store_true',
                        help='Also require >=54fps for120 visible canvas animation callbacks')
    args = parser.parse_args()
    if not args.consent_browser_trial or b'samsung,star2lte' not in Path('/sys/firmware/devicetree/base/compatible').read_bytes().split(b'\0'):
        parser.error('Explicit G965N visible-browser trial required')
    if os.geteuid() == 0:
        parser.error('Run as the desktop user, never root')
    if args.output.exists() or args.output.is_symlink():
        parser.error('Use a new private output path')
    os.umask(0o077)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    spec = importlib.util.spec_from_file_location('gpu', Path(__file__).with_name('gpu-validate.py'))
    gpu = importlib.util.module_from_spec(spec); spec.loader.exec_module(gpu)
    token = secrets.token_hex(16)
    route, post = '/' + token, '/' + token + '/result'
    original = Path(__file__).with_name('gpu-webgl.html').read_bytes()
    if original.count(b"fetch('/result'") != 1:
        raise RuntimeError('Unexpected WebGL result route')
    html = original.replace(b"fetch('/result'", ("fetch('" + post + "'").encode())
    reports = []; event = threading.Event(); requests = {'page': 0, 'result': 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused): pass
        def do_GET(self):
            if self.path != route:
                self.send_error(404); return
            requests['page'] += 1
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(html))); self.end_headers(); self.wfile.write(html)
        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if self.path != post or not 0 < length <= 8192:
                    raise ValueError('Unexpected result request')
                report = json.loads(self.rfile.read(length))
                if not isinstance(report, dict): raise ValueError('Expected object')
            except (ValueError, UnicodeError):
                self.send_error(400); return
            reports.append(report); requests['result'] += 1
            self.send_response(204); self.end_headers(); event.set()

    result = {'passed': False, 'scope': 'visible WebGL pixels only; not video decoding or browser endurance'}
    process = None; session = None; server = None; thread = None
    with tempfile.TemporaryDirectory(prefix='g965n-browser-', dir=args.output.parent) as work:
        logpath = args.output.with_name(args.output.name + '.webdriver-private.log')
        with logpath.open('xb') as log, gpu.hold_desktop_awake():
            try:
                server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
                with socket.socket() as reserve:
                    reserve.bind(('127.0.0.1', 0)); port = reserve.getsockname()[1]
                process = subprocess.Popen([str(args.geckodriver.resolve()), '--host', '127.0.0.1',
                                            '--port', str(port), '--profile-root', work],
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                base = 'http://127.0.0.1:' + str(port)
                deadline = time.monotonic() + 15
                while True:
                    if process.poll() is not None: raise RuntimeError('WebDriver exited during startup')
                    try:
                        if request(base, 'GET', '/status', timeout=1).get('ready'): break
                    except OSError: pass
                    if time.monotonic() >= deadline: raise RuntimeError('WebDriver readiness timeout')
                    time.sleep(.2)
                opened = request(base, 'POST', '/session', {'capabilities': {'alwaysMatch': {
                    'browserName': 'firefox', 'proxy': {'proxyType': 'direct'},
                    'moz:firefoxOptions': {'binary': '/usr/lib/firefox/firefox'}}}})
                session = opened['sessionId']; prefix = '/session/' + session
                capabilities = opened['capabilities']
                # Retain only graphics/sandbox policy entries from this throwaway
                # profile, never general profile contents or personal settings.
                policy = {}
                for name in ('prefs.js', 'user.js'):
                    prefs = Path(capabilities['moz:profile']) / name
                    if not prefs.exists(): continue
                    policy[name] = {}
                    for line in prefs.read_text().splitlines():
                        match = re.fullmatch(r'user_pref\("((?:gfx\.|webgl\.|security\.sandbox\.|layers\.acceleration\.)[^"\n]+)",\s*(.+)\);', line)
                        if match:
                            policy[name][match[1]] = json.loads(match[2])
                result['automation_graphics_policy'] = policy
                request(base, 'POST', prefix + '/url', {'url': 'http://127.0.0.1:' + str(server.server_port) + route})
                page = request(base, 'POST', prefix + '/execute/sync', {
                    'script': "return {visible:document.visibilityState==='visible',focused:document.hasFocus()};", 'args': []})
                if not event.wait(60): raise RuntimeError('Browser result timeout')
                report = reports[-1]
                cadence = None
                if args.cadence:
                    cadence = request(base, 'POST', prefix + '/execute/async', {'args': [], 'script': """
const done=arguments[arguments.length-1],gl=document.querySelector('canvas').getContext('webgl');
let times=[],warmup=30,n=0;
function frame(t){
 gl.clearColor((n%255)/255,0.3,0.6,1);gl.clear(gl.COLOR_BUFFER_BIT);gl.flush();n++;
 if(warmup>0)warmup--;else times.push(t);
 if(times.length<121){requestAnimationFrame(frame);return;}
 const delta=times.slice(1).map((v,i)=>v-times[i]).sort((a,b)=>a-b);
 done({frames:120,fps:120000/(times[120]-times[0]),median_ms:delta[60],p95_ms:delta[114],
       visible:document.visibilityState==='visible',focused:document.hasFocus(),context_lost:gl.isContextLost()});
}
requestAnimationFrame(frame);
"""})
                    result['cadence'] = cadence
                result.update(webgl=report, page=page,
                              headless=capabilities.get('moz:headless'),
                              browser_version=capabilities.get('browserVersion'),
                              passed=qualified(report, page, capabilities, policy) and
                              (cadence is None or (cadence['fps'] >= 54 and cadence['visible'] and
                               cadence['focused'] and not cadence['context_lost'])))
            except Exception as error:
                # Detailed driver/protocol output stays in the separate private log.
                result.update(error_type=type(error).__name__, error=str(error)[:160])
            finally:
                if session is not None:
                    try: request(base, 'DELETE', '/session/' + session, timeout=10)
                    except Exception: result['session_cleanup_failed'] = True
                if process is not None:
                    try: os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
                if server is not None: server.shutdown(); server.server_close()
                if thread is not None: thread.join(timeout=2)
                result['requests'] = requests
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream: json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps(result))
    raise SystemExit(0 if result['passed'] else 2)


if __name__ == '__main__': main()

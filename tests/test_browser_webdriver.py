# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import unittest
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('browser', Path(__file__).parents[1] / 'scripts/g965n/browser-webdriver-test.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class BrowserEvidenceTests(unittest.TestCase):
    def test_complete_visible_physical_gpu_pixels_required(self):
        good = {'passed': True, 'frames': 120, 'mismatches': 0, 'context_lost': False,
                'compared_bytes': 120*256*256*4, 'renderer': 'Mali-G72 (Panfrost)'}
        page = {'visible': True, 'focused': True}; caps = {'moz:headless': False}
        self.assertTrue(m.qualified(good, page, caps, {}))
        for key, value in [('passed', False), ('frames', 119), ('mismatches', 1),
                           ('mismatches', False), ('context_lost', True),
                           ('compared_bytes', 262144), ('renderer', None),
                           ('renderer', 'llvmpipe Mali'), ('renderer', 'SwiftShader'),
                           ('renderer', 'software')]:
            with self.subTest(key=key, value=value):
                self.assertFalse(m.qualified(dict(good, **{key:value}), page, caps, {}))
        for altered in [{'visible':False,'focused':True}, {'visible':True,'focused':False}, {}]:
            self.assertFalse(m.qualified(good, altered, caps, {}))
        for altered in [{'moz:headless':True}, {}]:
            self.assertFalse(m.qualified(good, page, altered, {}))

    def test_forced_gpu_or_disabled_sandbox_does_not_qualify(self):
        self.assertTrue(m.policy_unforced({'prefs.js':{}, 'user.js':{}}))
        for prefs in [{'webgl.force-enabled':True}, {'layers.acceleration.force-enabled':True},
                      {'security.sandbox.content.level':0}]:
            self.assertFalse(m.policy_unforced({'user.js':prefs}))
        self.assertTrue(m.policy_unforced({'user.js':{'webgl.force-enabled':False,'security.sandbox.content.level':4}}))

    def test_loopback_control_ignores_external_proxy_environment(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                body=json.dumps({'value':{'ready':True}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)))
                self.end_headers();self.wfile.write(body)
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            bad='http://127.0.0.1:1'
            with patch.dict(m.os.environ,{'http_proxy':bad,'HTTP_PROXY':bad,'no_proxy':'','NO_PROXY':''}):
                result=m.request('http://127.0.0.1:'+str(server.server_port),'GET','/status',timeout=2)
            self.assertEqual(result,{'ready':True})
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)


if __name__ == '__main__': unittest.main()

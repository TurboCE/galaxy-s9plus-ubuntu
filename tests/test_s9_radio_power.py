# SPDX-License-Identifier: GPL-2.0-only
import ast
import importlib.util
from pathlib import Path
import struct
import unittest

FILE=Path(__file__).resolve().parents[1]/'experiments/modem/ril-lab.py'
spec=importlib.util.spec_from_file_location('s9_radio',FILE)
ril=importlib.util.module_from_spec(spec);spec.loader.exec_module(ril)


class RadioWireFacts(unittest.TestCase):
    def test_own_stock_radio_normal_exec_frame(self):
        command,body,kind=ril.s9_radio_normal()
        frame=struct.pack('<HBBBBB',len(body)+7,1,255,command>>8,command&255,kind)+body
        self.assertEqual(frame,bytes.fromhex('090001ff0107010202'))

    def test_no_automatic_at_radio_toggle(self):
        strings=[n.value for n in ast.walk(ast.parse(FILE.read_text())) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
        self.assertNotIn('AT+CFUN=4',strings)
        self.assertNotIn('AT+CFUN=1',strings)
        self.assertIn('AT+CFUN?',strings)


if __name__=='__main__':unittest.main()

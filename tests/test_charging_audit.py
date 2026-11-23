# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[1]/'experiments/charging/audit-controls.py'
s=importlib.util.spec_from_file_location('charge_audit',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class AuditTests(unittest.TestCase):
    def test_disabled_audit_does_not_change_global_policy(self):
        with patch.object(m.shutil,'which',return_value='/usr/sbin/auditctl'),patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'enabled 0\n','')) as run:
            self.assertFalse(m.configure()['available'])
            self.assertEqual(run.call_count,1)
            self.assertEqual(run.call_args.args[0],['/usr/sbin/auditctl','-s'])

    def test_only_owned_watches_added_without_clearing_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in m.CONTROLS:(root/name).touch()
            real_path=Path
            def path(value):
                prefix='/sys/class/power_supply/max77705-charger'
                return root if str(value)==prefix else real_path(value)
            rules=[];calls=[]
            def run(args,**kwargs):
                calls.append(args)
                if args[1]=='-s':return subprocess.CompletedProcess(args,0,'enabled 1\n','')
                if args[1]=='-l':return subprocess.CompletedProcess(args,0,'-w /unrelated -p w -k existing\n'+'\n'.join(rules),'')
                self.assertEqual(args[1],'-w');self.assertEqual(args[-1],m.KEY)
                rules.append(' '.join(args[1:]))
                return subprocess.CompletedProcess(args,0,'','')
            with patch.object(m,'Path',side_effect=path),patch.object(m.shutil,'which',return_value='/usr/sbin/auditctl'),patch.object(m.subprocess,'run',side_effect=run):
                self.assertTrue(m.configure()['available']);self.assertEqual(len(rules),3)
                self.assertTrue(m.configure()['available']);self.assertEqual(len(rules),3)
            self.assertFalse(any('-D' in call or '-e' in call for call in calls))

    def test_immutable_configuration_not_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in m.CONTROLS:(root/name).touch()
            with patch.object(m,'Path',return_value=root),patch.object(m.shutil,'which',return_value='/usr/sbin/auditctl'),patch.object(m.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0,'enabled 2\n',''),subprocess.CompletedProcess([],0,'','')]) as run:
                self.assertFalse(m.configure()['available']);self.assertEqual(run.call_count,2)

if __name__=='__main__':unittest.main()

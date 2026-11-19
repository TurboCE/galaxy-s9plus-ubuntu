# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parents[1]/'scripts/g965n/kernel-health.py'
s=importlib.util.spec_from_file_location('kh',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class KernelHealthTests(unittest.TestCase):
    def test_early_boot_missing_is_not_clean_kernel_or_private_output(self):
        logs={k:'' for k in m.COMMANDS}
        logs['ring']='Linux version test\nCPU: Unexpected variation in SYS_TEST\nprivate-subscriber-450081234567890\nMCU_RESP still high\n'
        logs['journal']='late module started\n'
        logs['ring-warnings']='warning\n'
        result=m.summary(logs)
        self.assertTrue(result['journal_early_boot_missing'])
        self.assertEqual(result['ring_error_priority_lines'],0)
        self.assertEqual(result['ring_warning_priority_lines'],1)
        self.assertEqual(result['known_message_counts']['cpu_register_variations'],1)
        self.assertFalse(result['all_hardware_qualified'])
        self.assertNotIn('450081234567890',json.dumps(result))
        logs['ring']='late ring only\n'
        self.assertFalse(m.summary(logs)['ring_boot_header_present'])

    def test_exclusive_private_files_and_failed_capture_do_not_report_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp).resolve();p.chmod(0o700)
            m.write_private(p/'old','earlier evidence')
            self.assertEqual(stat.S_IMODE((p/'old').stat().st_mode),0o600)
            with self.assertRaises(FileExistsError):m.write_private(p/'old','overwrite')
            (p/'link').symlink_to(p/'old')
            with self.assertRaises(OSError):m.write_private(p/'link','bad')
            p.chmod(0o755)
            with self.assertRaises(ValueError):m.write_private(p/'open','bad')
            p.chmod(0o700)
            with patch.object(m.subprocess,'run',side_effect=RuntimeError('capture failed')):
                with self.assertRaises(RuntimeError):m.collect(p)
            self.assertFalse((p/'summary.json').exists())

    def test_current_messages_are_counted_separately_in_ring_and_journal(self):
        logs = {key: '' for key in m.COMMANDS}
        hub = 'zrn-bbd: MCU_RESP remained high after 1 standby attempt(s); reset unconfirmed'
        pll = 's9p-g3d: PLL_G3D did not lock for 260000 kHz (con0=80a00402)'
        rollback = 's9p-g3d: PLL rollback failed (-110), con0=81c71a00'
        gpio = 'WARNING: drivers/gpio/gpiolib.c:429 at gpiochip_get_direction+0x30/0x3c'
        qos = 'g965n-mif: vendor bus QoS is not implemented'
        logs['ring'] = '\n'.join((hub, gpio, qos, qos))
        logs['journal'] = '\n'.join((hub, 'MCU_RESP still high', pll, rollback, qos, 'PMC reset unconfirmed'))
        result = m.summary(logs)
        ring = result['known_message_counts']
        journal = result['journal_known_message_counts']
        self.assertEqual(ring['hub_reset_unconfirmed'], 1)
        self.assertEqual(journal['hub_reset_unconfirmed'], 2)
        self.assertEqual(ring['gpu_pll_lock_failures'], 0)
        self.assertEqual(journal['gpu_pll_lock_failures'], 1)
        self.assertEqual(journal['gpu_pll_rollback_failures'], 1)
        self.assertEqual(ring['gpio_direction_warnings'], 1)
        self.assertEqual(ring['modem_qos_unimplemented'], 2)
        self.assertEqual(journal['modem_qos_unimplemented'], 1)


if __name__=='__main__':unittest.main()

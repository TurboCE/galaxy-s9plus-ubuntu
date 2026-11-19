#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Patch copies and compile actual controller data, never touch a device/cache."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SPEC=importlib.util.spec_from_file_location('pinctrl_apply',HERE/'apply.py')
A=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(A)
MANIFEST=json.loads((HERE/'SOURCES.json').read_text())
FIXTURE=Path(os.environ.get('PINCTRL_FIXTURE',str(ROOT/'.local/context/pinctrl-pristine')))

STUBS=r'''
#include <assert.h>
#include <stddef.h>
#define __initconst
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
enum { N, W, G };
struct samsung_pin_bank_data {unsigned nr_pins;unsigned offset;const char *name;unsigned eint_type;unsigned eint_offset;};
#define EXYNOS850_PIN_BANK_EINTN(n,o,name) {n,o,name,N,0}
#define EXYNOS850_PIN_BANK_EINTW(n,o,name,e) {n,o,name,W,e}
#define EXYNOS850_PIN_BANK_EINTG(n,o,name,e) {n,o,name,G,e}
static int gpio_calls,wake_calls;
static int exynos_eint_gpio_init(void *p) {gpio_calls++;return -22;}
static int exynos_eint_wkup_init(void *p) {wake_calls++;return 0;}
static void exynos_pinctrl_suspend(void *p) {}
static void exynos_pinctrl_resume(void *p) {}
struct samsung_pin_ctrl {const struct samsung_pin_bank_data *pin_banks;unsigned nr_banks;int (*eint_wkup_init)(void *);int (*eint_gpio_init)(void *);void (*suspend)(void *);void (*resume)(void *);};
'''
MAIN=r'''
int main(void) {
 unsigned wrong_gpio_init=0;
 assert(ARRAY_SIZE(exynos9810_pin_ctrl)==9);
 for(unsigned i=0;i<9;i++) {
  const struct samsung_pin_ctrl *c=&exynos9810_pin_ctrl[i];
  unsigned has_gpio=0;
  for(unsigned j=0;j<c->nr_banks;j++)has_gpio|=c->pin_banks[j].eint_type==G;
  if(!has_gpio&&c->eint_gpio_init)wrong_gpio_init++;
  if(i==0||i==3) {
   assert(!has_gpio);assert(c->eint_wkup_init==exynos_eint_wkup_init);
   assert(c->suspend==exynos_pinctrl_suspend&&c->resume==exynos_pinctrl_resume);
   assert(c->eint_wkup_init(NULL)==0);
   if(c->eint_gpio_init)assert(c->eint_gpio_init(NULL)==-22);
  }
 }
 assert(wrong_gpio_init==EXPECTED);
 assert(gpio_calls==EXPECTED&&wake_calls==2);
 assert(exynos9810_pin_banks0[6].nr_pins==2);
 return 0;
}
'''


def data_section(text):
    start=text.index('static const struct samsung_pin_bank_data exynos9810_pin_banks0[]')
    end=text.index('\n};',text.index('static const struct samsung_pin_ctrl exynos9810_pin_ctrl[]',start))+3
    return text[start:end]


class PinctrlTests(unittest.TestCase):
    def setUp(self):
        if not all((FIXTURE/Path(e['path']).name).is_file() for e in MANIFEST['files']):
            self.skipTest('Set PINCTRL_FIXTURE to exact pristine source copies')

    def prepare(self,root):
        for e in MANIFEST['files']:
            p=root/e['path'];p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes((FIXTURE/p.name).read_bytes())

    def test_patch_idempotence_drift_and_narrow_change(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.prepare(root)
            self.assertEqual(A.apply(root,True),2)
            self.assertEqual(A.apply(root),2);self.assertEqual(A.apply(root),0)
            for e in MANIFEST['files']:
                before=(FIXTURE/Path(e['path']).name).read_text();after=(root/e['path']).read_text()
                self.assertEqual(before.splitlines()[:10],after.splitlines()[:10])
                self.assertEqual(A.checksum(root/e['path']),e['after_sha256'])
                if e['path'].endswith('.c'):
                    self.assertEqual(before.replace(data_section(before),''),after.replace(data_section(after),''))
                    self.assertEqual(data_section(before).split('static const struct samsung_pin_ctrl')[0],data_section(after).split('static const struct samsung_pin_ctrl')[0])
                else:
                    a=before.index('\tgpa4:');b=before.index('\n\t};',a)
                    x=after.index('\tgpa4:');y=after.index('\n\t};',x)
                    self.assertEqual(before[:a]+before[b:],after[:x]+after[y:])
            first=root/MANIFEST['files'][0]['path'];second=root/MANIFEST['files'][1]['path']
            first.write_bytes((FIXTURE/first.name).read_bytes());second.write_text('foreign drift')
            with self.assertRaises(RuntimeError):A.apply(root)
            self.assertEqual(first.read_bytes(),(FIXTURE/first.name).read_bytes())

    def test_actual_controller_data_original_fails_patched_routes_only_wakeup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.prepare(root)
            path=root/MANIFEST['files'][0]['path'];original=path.read_text()
            A.apply(root);patched=path.read_text()
            for text,expected in [(original,2),(patched,0)]:
                c=root/'check.c';exe=root/'check'
                c.write_text(STUBS+'\n'+data_section(text)+'\n#define EXPECTED '+str(expected)+'\n'+MAIN)
                subprocess.run([os.environ.get('CC','cc'),'-std=c11','-fsanitize=address,undefined',str(c),'-o',str(exe)],check=True,capture_output=True)
                subprocess.run([str(exe)],check=True,capture_output=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})

    def test_gpa4_matches_exact_pinned_lineage_pin_order(self):
        lineage=Path(os.environ.get('LINEAGE_KERNEL_SOURCE','/Users/yongseok/Workspace/Codex/Galaxy-S9-Ubuntu/references/lineage-exynos9810'))
        if not (lineage/'.git').exists():self.skipTest('Set LINEAGE_KERNEL_SOURCE for independent pinned stock cross-check')
        commit=MANIFEST['lineage_commit']
        path='arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts'
        text=subprocess.check_output(['git','-C',str(lineage),'show',commit+':'+path],text=True)
        block=re.search(r'\n\s*gpa4\s*\{([^}]+)\}',text).group(1)
        cells=re.search(r'interrupts\s*=\s*<([^>]+)>',block).group(1).split()
        numbers=[int(n,0) for n in cells]
        self.assertEqual(numbers,[0,446,0,0,447,0])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.prepare(root);A.apply(root)
            patched=(root/MANIFEST['files'][1]['path']).read_text()
            block=re.search(r'gpa4: gpa4-gpio-bank\s*\{([^}]+)\}',patched).group(1)
            self.assertIn('interrupt-parent = <&gic>;',block)
            self.assertEqual(re.findall(r'GIC_SPI\s+(\d+)\s+IRQ_TYPE_LEVEL_HIGH',block),['446','447'])
            self.assertEqual(block.count('interrupt-controller;'),1)


if __name__=='__main__':unittest.main()

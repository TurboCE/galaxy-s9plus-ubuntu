# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual reviewed C functions against faultable API stubs, without hardware."""
import argparse
import importlib.util
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pmic_apply', HERE / 'apply.py')
patcher = importlib.util.module_from_spec(spec); spec.loader.exec_module(patcher)


def function(text, name):
    start = text.index(name + '(')
    start = text.rfind('\n', 0, start) + 1
    return text[start:text.index('\n}', text.index('{', start)) + 2]


SHIM = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#ifndef EREMOTEIO
#define EREMOTEIO 121
#endif
typedef uint32_t u32;
#define GFP_KERNEL 0
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define LED_OFF 0
#define LED_ON 1
#define LED_COLOR_ID_RED 1
#define LED_COLOR_ID_GREEN 2
#define LED_COLOR_ID_RGB 8
#define MAX77705_LED_NUM_LEDS 4
#define MAX77705_LED_EN_MASK 3
#define MAX77705_LED_EN_SHIFT(reg) ((reg)*2)
#define MAX77705_LED_REG_BRIGHTNESS(reg) ((reg)+1)
#define MAX77705_LED_MAX_BRIGHTNESS 255
#define MAX77705_RGBLED_REG_LEDEN 0
#define MAX77705_RGBLED_REG_LEDBLNK 6
#define MAX77705_RGB_DELAY_100_STEP_LIM 500
#define MAX77705_RGB_DELAY_100_STEP_COUNT 4
#define MAX77705_RGB_DELAY_100_STEP 100
#define MAX77705_RGB_DELAY_250_STEP_LIM 3250
#define MAX77705_RGB_DELAY_250_STEP 250
#define MAX77705_RGB_DELAY_500_STEP 500
#define MAX77705_RGB_DELAY_500_STEP_COUNT 10
#define MAX77705_RGB_DELAY_500_STEP_LIM 5000
#define MAX77705_RGB_DELAY_1000_STEP_LIM 8000
#define MAX77705_RGB_DELAY_1000_STEP_COUNT 13
#define MAX77705_RGB_DELAY_1000_STEP 1000
#define MAX77705_RGB_DELAY_2000_STEP 2000
#define MAX77705_RGB_DELAY_2000_STEP_LIM 12000
#define TYPE_MAX77693 0
#define TYPE_MAX77705 1
#define TYPE_MAX77843 2
#define MAX77705_PMIC_REG_MAINCTRL1 0x02
#define MAX77705_MAINCTRL1_BIASEN_MASK 0x80
#define MAX77843_SYS_REG_MAINCTRL1 0x02
#define MAX77843_MAINCTRL1_BIASEN_MASK 0x80
#define MAINCTRL1_BIASEN_SHIFT 7
#define dev_err(...) ((void)0)
#define str_enable_disable(on) ((on)?"enable":"disable")
struct device {int unused;};
struct regmap {unsigned int regs[256];};
struct mc_subled {unsigned int channel,brightness,color_index,intensity;};
enum led_brightness { STUB_OFF=0, STUB_ON=1 };
struct led_classdev {unsigned int max_brightness;
 int (*brightness_set_blocking)(struct led_classdev*,enum led_brightness);
 int (*blink_set)(struct led_classdev*,unsigned long*,unsigned long*);};
struct led_classdev_mc {struct led_classdev led_cdev;struct mc_subled *subled_info;int num_colors;};
#define lcdev_to_mccdev(p) container_of(p,struct led_classdev_mc,led_cdev)
struct fwnode_handle {u32 color,reg;int reg_error,color_error,n;struct fwnode_handle *children[3];};
struct led_init_data {struct fwnode_handle *fwnode;};
struct max77693_haptic {int dev_type;struct regmap *regmap_haptic;struct device *dev;void *motor_reg;};
struct input_dev {struct max77693_haptic *data;};
static struct max77693_haptic *input_get_drvdata(struct input_dev *d){return d->data;}
static int updates,writes,registrations,regulator_calls,update_error_at,write_error_at;
static int update_error=-EIO,regulator_error,registration_error;
static unsigned int last_reg,last_mask,last_value;
static struct led_classdev_mc *expected_mc,*registered_mc;
static struct led_classdev *registered_single;
static int regmap_update_bits(struct regmap*m,unsigned int r,unsigned int mask,unsigned int value){
 updates++;last_reg=r;last_mask=mask;last_value=value;
 if(updates==update_error_at)return update_error;
 m->regs[r]=(m->regs[r]&~mask)|(value&mask);return 0;}
static int regmap_write(struct regmap*m,unsigned int r,unsigned int value){
 writes++;last_reg=r;last_value=value;if(writes==write_error_at)return -EREMOTEIO;
 m->regs[r]=value;return 0;}
static int regulator_enable(void*p){(void)p;regulator_calls++;return regulator_error;}
static void *devm_kzalloc(struct device*d,size_t n,int flags){(void)d;(void)flags;return calloc(1,n);}
static void *devm_kcalloc(struct device*d,size_t n,size_t size,int flags){(void)d;(void)flags;return calloc(n,size);}
static int dev_err_probe(struct device*d,int err,const char*fmt,...){(void)d;(void)fmt;return err;}
static int fwnode_property_read_u32(struct fwnode_handle*n,const char*name,u32*v){
 if(!strcmp(name,"reg")){if(n->reg_error)return n->reg_error;*v=n->reg;return 0;}
 if(n->color_error)return n->color_error;*v=n->color;return 0;}
#define to_of_node(np) (np)
static int of_get_available_child_count(struct fwnode_handle*n){return n->n;}
#define fwnode_for_each_child_node(np,child) for(int idx=0;idx<(np)->n&&((child)=(np)->children[idx]);idx++)
static int devm_led_classdev_register_ext(struct device*d,struct led_classdev*c,struct led_init_data*i){
 (void)d;(void)i;registrations++;registered_single=c;return registration_error;}
static int devm_led_classdev_multicolor_register_ext(struct device*d,struct led_classdev_mc*c,struct led_init_data*i){
 (void)d;(void)i;registrations++;expected_mc=c;registered_mc=c;return registration_error;}
static void led_mc_calc_color_components(struct led_classdev_mc*c,enum led_brightness b){
 assert(c==expected_mc);for(int i=0;i<c->num_colors;i++)c->subled_info[i].brightness=b;}
'''

HARNESS = r'''
static void reset(void){updates=writes=registrations=regulator_calls=0;update_error_at=write_error_at=0;
 update_error=-EIO;regulator_error=registration_error=0;expected_mc=registered_mc=NULL;registered_single=NULL;}
int main(int argc,char**argv){assert(argc==2);reset();const char*s=argv[1];struct regmap map={0};struct device dev={0};
 struct fwnode_handle red={.color=LED_COLOR_ID_RED,.reg=1},green={.color=LED_COLOR_ID_GREEN,.reg=2};
 struct fwnode_handle rgb={.color=LED_COLOR_ID_RGB,.reg=0,.n=2,.children={&red,&green}};
 struct max77693_haptic h={.dev_type=TYPE_MAX77705,.regmap_haptic=&map,.dev=&dev};struct input_dev input={.data=&h};
 if(!strcmp(s,"multi-off-object")){map.regs[0]=255;assert(max77705_add_led(&dev,&map,&rgb)==0);
  assert(registered_mc&&updates==2&&writes==0);assert(map.regs[0]==(255u&~(12u|48u)));}
 else if(!strcmp(s,"single-off-object")){map.regs[0]=255;assert(max77705_add_led(&dev,&map,&red)==0);
  assert(registered_single&&updates==1&&map.regs[0]==(255u&~12u));}
 else if(!strcmp(s,"single-blink-object")){struct max77705_led led={.regmap=&map};unsigned long on=600,off=1000;
  assert(max77705_rgb_blink_single(&led.cdev,&on,&off)==0);assert(writes==1&&last_reg==6&&last_value==0x42);}
 else if(!strcmp(s,"multi-blink-object")){struct max77705_led led={.regmap=&map};unsigned long on=600,off=1000;
  assert(max77705_rgb_blink_multi(&led.mcdev.led_cdev,&on,&off)==0);assert(writes==1&&last_reg==6&&last_value==0x42);}
 else if(!strcmp(s,"masked-brightness")){struct mc_subled info={.channel=2,.brightness=29};map.regs[0]=255;
  assert(max77705_led_brightness_set(&map,&info,1)==0);assert(map.regs[0]==0xdf&&last_mask==0x30&&last_value==0x10);
  assert(map.regs[3]==29&&writes==1);}
 else if(!strcmp(s,"parse-error-unwind")){red.reg=0;assert(max77705_add_led(&dev,&map,&red)==-EINVAL);
  assert(!registrations&&!updates&&!writes);red.reg=1;red.color_error=-EREMOTEIO;
  assert(max77705_add_led(&dev,&map,&red)==-EREMOTEIO);assert(!registrations&&!updates&&!writes);}
 else if(!strcmp(s,"registration-error")){registration_error=-EIO;assert(max77705_add_led(&dev,&map,&rgb)==-EIO);assert(!updates&&!writes);}
 else if(!strcmp(s,"first-update-error")){struct mc_subled info[2]={{.channel=1,.brightness=0},{.channel=2,.brightness=0}};
  update_error_at=1;assert(max77705_led_brightness_set(&map,info,2)==-EIO);assert(updates==1&&!writes);}
 else if(!strcmp(s,"brightness-write-error")){struct mc_subled info={.channel=1,.brightness=10};write_error_at=1;
  assert(max77705_led_brightness_set(&map,&info,1)==-EREMOTEIO);assert(writes==1&&!updates);}
 else if(!strcmp(s,"bias-77705")){map.regs[2]=0x5a;assert(max77843_haptic_bias(&h,true)==0);
  assert(last_reg==2&&last_mask==0x80&&last_value==0x80&&map.regs[2]==0xda);
  assert(max77843_haptic_bias(&h,false)==0&&map.regs[2]==0x5a);assert(updates==2);}
 else if(!strcmp(s,"bias-77843-unchanged")){h.dev_type=TYPE_MAX77843;map.regs[2]=0x33;
  assert(max77843_haptic_bias(&h,true)==0&&map.regs[2]==0xb3);assert(last_reg==2&&last_mask==0x80);
  assert(max77843_haptic_bias(&h,false)==0&&map.regs[2]==0x33);}
 else if(!strcmp(s,"other-chip-no-bias")){h.dev_type=TYPE_MAX77693;assert(max77843_haptic_bias(&h,true)==0);assert(!updates);}
 else if(!strcmp(s,"bias-enable-error")){update_error_at=1;assert(max77693_haptic_open(&input)==-EIO);assert(updates==1&&!regulator_calls);}
 else if(!strcmp(s,"supply-enable-unwind")){map.regs[2]=0x35;regulator_error=-ENODEV;
  assert(max77693_haptic_open(&input)==-ENODEV);assert(updates==2&&regulator_calls==1&&map.regs[2]==0x35);}
 else if(!strcmp(s,"unwind-secondary-error")){regulator_error=-ENODEV;update_error_at=2;update_error=-EREMOTEIO;
  assert(max77693_haptic_open(&input)==-ENODEV);assert(updates==2&&regulator_calls==1);}
 else if(!strcmp(s,"77843-error-policy-unchanged")){h.dev_type=TYPE_MAX77843;regulator_error=-ENODEV;
  assert(max77693_haptic_open(&input)==-ENODEV);assert(updates==1&&regulator_calls==1);}
 else assert(!"unknown scenario");return 0;}
'''


class CorrectnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('cc')
        if not compiler:
            raise RuntimeError('Host C compiler required; nothing is installed by this test')
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.tree = Path(cls.temp.name) / 'kernel'; cls.tree.mkdir()
        for relative in [entry['path'] for entry in json.loads((HERE / 'SOURCES.json').read_text())['files']]:
            target = cls.tree / relative; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SOURCE / relative, target)
        patcher.apply(cls.tree)
        led = (cls.tree / 'drivers/leds/leds-max77705.c').read_text()
        haptic = (cls.tree / 'drivers/input/misc/max77693-haptic.c').read_text()
        structure = led[led.index('struct max77705_led {'):led.index('\n};', led.index('struct max77705_led {')) + 3]
        code = SHIM + '\n' + structure
        for name in ['max77705_rgb_blink_apply', 'max77705_rgb_blink_single', 'max77705_rgb_blink_multi',
                     'max77705_led_brightness_set', 'max77705_led_brightness_set_single',
                     'max77705_led_brightness_set_multi', 'max77705_parse_subled', 'max77705_add_led']:
            code += '\n' + function(led, name)
        for name in ['max77843_haptic_bias', 'max77693_haptic_open']:
            code += '\n' + function(haptic, name)
        c = Path(cls.temp.name) / 'actual-pmic.c'; c.write_text(code + '\n' + HARNESS)
        cls.binary = Path(cls.temp.name) / 'actual-pmic'
        result = subprocess.run([compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                                 '-Wno-misleading-indentation', str(c), '-o', str(cls.binary)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    def test_mfd_cell_array_and_real_charger_unchanged(self):
        manifest = json.loads((HERE / 'SOURCES.json').read_text())
        entry = next(e for e in manifest['files'] if e['path'] == 'drivers/mfd/max77705.c')
        after = (self.tree / entry['path']).read_text()
        phantom = '\tMFD_CELL_OF("max77705-charger", NULL, NULL, 0, 0, "maxim,max77705-charger"),\n'
        # Reconstruct the exact pinned preimage, including its complete IRQ/probe code.
        anchor = '\tMFD_CELL_OF("max77705-rgb", NULL, NULL, 0, 0, "maxim,max77705-rgb"),\n'
        self.assertEqual(after.count(anchor), 1)
        before = after.replace(anchor, anchor + phantom, 1)
        self.assertEqual(hashlib.sha256(before.encode()).hexdigest(), entry['before_sha256'])
        self.assertEqual(before.replace(phantom, '', 1), after)
        self.assertIn('domain = regmap_irq_get_domain(irq_data);', after)
        self.assertIn('max77705_devs, ARRAY_SIZE(max77705_devs),', after)
        self.assertIn('NULL, 0, domain);', after)
        refs = manifest['topology_references']
        charger = (SOURCE / refs['charger_i2c_path']).read_bytes()
        self.assertEqual(hashlib.sha256(charger).hexdigest(), refs['charger_i2c_sha256'])
        self.assertIn(b'module_i2c_driver(max77705_charger_driver);', charger)
        self.assertNotIn(b'module_platform_driver', charger)
        dts = (HERE.parents[1] / refs['port_dts_path']).read_bytes()
        self.assertEqual(hashlib.sha256(dts).hexdigest(), refs['port_dts_sha256'])
        block = re.search(rb'max77705_charger: charger@69\s*\{([^}]+)\}', dts).group(1)
        for value in [b'reg = <0x69>;', b'interrupt-parent = <&max77705>;', b'interrupts = <0>;', b'monitored-battery = <&battery>;']:
            self.assertIn(value, block)
        def array(text, marker):
            start = text.index(marker)
            return text[start:text.index('\n};', start) + 3]
        irq = array(after, 'static const struct regmap_irq max77705_irqs[]')
        shim = r'''#include <assert.h>
#include <string.h>
#include <stddef.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define BIT(n) (1U<<(n))
#define MAX77705_SRC_IRQ_CHG BIT(0)
#define MAX77705_SRC_IRQ_TOP BIT(1)
#define MAX77705_SRC_IRQ_FG BIT(2)
#define MAX77705_SRC_IRQ_USBC BIT(3)
struct mfd_cell { const char *name; const void *resources; const void *pdata; unsigned size; int id; const char *compatible; };
#define MFD_CELL_OF(n,r,p,s,i,c) {n,r,p,s,i,c}
struct regmap_irq { unsigned mask; };
'''
        main = r'''int main(void) {
 assert(ARRAY_SIZE(max77705_devs)==EXPECTED);
 assert(!strcmp(max77705_devs[0].name,"max77705-rgb"));
 assert(!strcmp(max77705_devs[0].compatible,"maxim,max77705-rgb"));
 assert(!strcmp(max77705_devs[EXPECTED-1].name,"max77705-haptic"));
 assert(!strcmp(max77705_devs[EXPECTED-1].compatible,"maxim,max77705-haptic"));
 for(unsigned i=0;i<EXPECTED;i++)assert(!max77705_devs[i].resources&&!max77705_devs[i].pdata&&!max77705_devs[i].size&&!max77705_devs[i].id);
 if(EXPECTED==2)for(unsigned i=0;i<EXPECTED;i++)assert(strcmp(max77705_devs[i].name,"max77705-charger"));
 else assert(!strcmp(max77705_devs[1].name,"max77705-charger"));
 assert(ARRAY_SIZE(max77705_irqs)==4);
 for(unsigned i=0;i<4;i++)assert(max77705_irqs[i].mask==BIT(i));
 return 0;
}'''
        for text, expected in [(before, 3), (after, 2)]:
            with tempfile.TemporaryDirectory() as td:
                c = Path(td) / 'mfd.c'; binary = Path(td) / 'mfd'
                c.write_text(shim + '\n' + array(text, 'static struct mfd_cell max77705_devs[]') + '\n' + irq + '\n#define EXPECTED ' + str(expected) + '\n' + main)
                subprocess.run([shutil.which('cc'), '-std=c11', '-fsanitize=address,undefined', str(c), '-o', str(binary)], check=True, capture_output=True)
                subprocess.run([str(binary)], check=True, capture_output=True)

    def test_actual_production_functions(self):
        scenarios = ['multi-off-object', 'single-off-object', 'single-blink-object', 'multi-blink-object',
                     'masked-brightness', 'parse-error-unwind', 'registration-error', 'first-update-error',
                     'brightness-write-error', 'bias-77705', 'bias-77843-unchanged', 'other-chip-no-bias',
                     'bias-enable-error', 'supply-enable-unwind', 'unwind-secondary-error', '77843-error-policy-unchanged']
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                subprocess.run([str(self.binary), scenario], check=True, capture_output=True, text=True, timeout=5)

    def test_repeat_is_idempotent_and_drift_is_rejected_before_any_patch(self):
        self.assertEqual(patcher.apply(self.tree), 0)
        path = self.tree / 'drivers/leds/leds-max77705.c'; original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n/* unreviewed */\n')
            with self.assertRaisesRegex(RuntimeError, 'drift'):
                patcher.prepare(self.tree)
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-source', type=Path, required=True)
    args = parser.parse_args(); SOURCE = args.kernel_source.resolve()
    unittest.main(argv=[__file__])

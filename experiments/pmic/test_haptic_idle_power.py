#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual lazy-power functions with persistent clients and injected faults."""
import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', type=Path, required=True)
a = p.parse_args()
s = a.source.read_text()
names = ['g965n_haptic_idle_init', 'g965n_haptic_power_on', 'g965n_haptic_power_off', 'max77693_haptic_enable',
         'max77693_haptic_disable', 'max77693_haptic_open', 'max77693_haptic_close']
functions = []
for name in names:
    start = s.index('static ', s.index(name + '(') - 15)
    functions.append(s[start:s.index('\n}', start) + 2])
shim = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#define TYPE_MAX77705 1
#define dev_err(...) ((void)0)
struct work_struct { int unused; };
struct pwm_state { unsigned long period,duty_cycle; bool enabled; };
struct max77693_haptic { int dev_type; bool enabled,motor_powered,motor_bias; void *motor_reg,*dev,*pwm_dev; unsigned pwm_duty; struct work_struct work; };
struct input_dev { struct max77693_haptic *data; };
static int supply,bias,pwm,motor,fail;
static int max77843_haptic_bias(struct max77693_haptic *h,bool on){(void)h;if(fail==(on?1:6))return -5;bias=on;return 0;}
static int regulator_enable(void *r){(void)r;if(fail==2)return -5;assert(!supply);supply=1;return 0;}
static int regulator_disable(void *r){(void)r;if(fail==7)return -5;assert(supply);supply=0;return 0;}
static void pwm_init_state(void *p,struct pwm_state *s){(void)p;s->period=48828;}
static int pwm_apply_might_sleep(void *p,struct pwm_state *s){(void)p;(void)s;if(fail==3)return -5;assert(supply&&bias);pwm=1;return 0;}
static void pwm_disable(void *p){(void)p;pwm=0;}
static int max77693_haptic_lowsys(struct max77693_haptic *h,bool on){(void)h;(void)on;return 0;}
static int max77693_haptic_configure(struct max77693_haptic *h,bool on){(void)h;if(fail==(on?4:5))return -5;motor=on;return 0;}
static struct max77693_haptic *input_get_drvdata(struct input_dev *d){return d->data;}
static void cancel_work_sync(struct work_struct *w){(void)w;}
'''
main = r'''
int main(void){
 struct max77693_haptic h={.dev_type=TYPE_MAX77705};struct input_dev d={&h};
 motor=1;bias=1;assert(!g965n_haptic_idle_init(&h));assert(!motor&&!bias);
 fail=5;assert(g965n_haptic_idle_init(&h)==-5);fail=6;assert(g965n_haptic_idle_init(&h)==-5);fail=0;
 assert(!max77693_haptic_open(&d));assert(!supply&&!bias);
 for(int i=0;i<100;i++){
  max77693_haptic_enable(&h);assert(h.enabled&&supply&&bias&&pwm&&motor);
  max77693_haptic_enable(&h);
  max77693_haptic_disable(&h);assert(!h.enabled&&!supply&&!bias&&!pwm);
 }
 max77693_haptic_close(&d);max77693_haptic_close(&d);assert(!supply&&!bias);
 for(int f=1;f<=4;f++){
  fail=f;max77693_haptic_enable(&h);assert(!h.enabled&&!supply&&!bias&&!pwm);
  fail=0;max77693_haptic_enable(&h);assert(h.enabled);max77693_haptic_disable(&h);
 }
 for(int f=5;f<=7;f++){
  fail=0;max77693_haptic_enable(&h);assert(h.enabled);
  fail=f;max77693_haptic_disable(&h);assert(!pwm&&!h.enabled);
  if(f==5)assert(!supply&&!bias); /* PMIC stop failure still cuts real power */
  if(f==6)assert(!supply&&h.motor_bias);
  if(f==7)assert(supply&&h.motor_powered&&!bias);
  fail=0;max77693_haptic_close(&d);assert(!supply&&!bias&&!h.motor_powered&&!h.motor_bias);
 }
 puts("Persistent-open idle off; 100 cycles, enable failures and stop-failure cleanup passed");
}
'''
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'test.c').write_text(shim + '\n'.join(functions) + main)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-g', str(root / 'test.c'), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True)

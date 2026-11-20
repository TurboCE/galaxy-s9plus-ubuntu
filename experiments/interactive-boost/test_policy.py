#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual worker/event/match code at expiry, stale work and error boundaries."""
from pathlib import Path
import subprocess
import tempfile

s = Path(__file__).with_name('g965n-interactive-boost.c').read_text()
functions = []
for name, prefix in [('release_floors', 'static void'), ('boost_apply', 'static void'),
                     ('boost_release', 'static void'), ('boost_match', 'static bool'),
                     ('boost_event', 'static void')]:
    start = s.index('\n' + prefix + ' ' + name + '(')
    functions.append(s[start:s.index('\n}', start) + 2])
ids = s[s.index('static const struct input_device_id boost_ids[]'):s.index('static struct input_handler boost_handler')]
shim = r'''
#include <assert.h>
#include <stdbool.h>
#include <limits.h>
#include <stdio.h>
#define FREQ_QOS_MIN_DEFAULT_VALUE 0
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define time_before(a,b) ((long)((a)-(b))<0)
#define time_after_eq(a,b) (!time_before(a,b))
#define msecs_to_jiffies(x) (x)
#define pr_err_ratelimited(...) ((void)0)
#define EV_KEY 1
#define EV_ABS 3
#define EV_FF 21
#define ABS_MT_POSITION_X 35
#define ABS_MT_POSITION_Y 36
#define KEY_A 30
#define KEY_LEFTMETA 125
struct work_struct {int unused;};
struct delayed_work {int unused;};
struct input_handle {int unused;};
struct input_handler {int unused;};
struct input_device_id {unsigned long flags;unsigned long evbit[4];};
#define INPUT_DEVICE_ID_MATCH_EVBIT 1
#define BIT_MASK(b) (1ul<<(b))
struct input_dev {unsigned long evbit[4],absbit[4],keybit[4];};
struct freq_qos_request {unsigned value;};
static struct freq_qos_request floors[2];
static unsigned ceiling[]={1499333,2327000}, hold_ms=500;
static unsigned long last_input,jiffies,rearm;
static bool active,stopping;
static int boost_lock,system_wq,queued,fail_second,updates;
static struct work_struct apply_work;
static struct delayed_work release_work;
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
static int freq_qos_update_request(struct freq_qos_request *q,unsigned v){updates++;if(fail_second&&q==&floors[1]&&v){fail_second=0;return -5;}q->value=v;return 0;}
static void mod_delayed_work(int w,struct delayed_work *d,unsigned long t){(void)w;(void)d;rearm=t;}
static void schedule_work(struct work_struct *w){(void)w;queued++;}
static bool test_bit(unsigned b,const unsigned long *a){return (a[b/(sizeof(long)*8)]>>(b%(sizeof(long)*8)))&1;}
static void bit(unsigned b,unsigned long *a){a[b/(sizeof(long)*8)]|=1ul<<(b%(sizeof(long)*8));}
'''
main = r'''
static bool table_matches(struct input_dev *dev){for(const struct input_device_id *id=boost_ids;id->flags;id++)if((dev->evbit[0]&id->evbit[0])==id->evbit[0]&&boost_match(0,dev))return true;return false;}

int main(void){
 struct input_dev d={0};
 assert(!boost_match(0,&d));assert(!table_matches(&d));bit(EV_FF,d.evbit);assert(!boost_match(0,&d));
 bit(EV_KEY,d.evbit);bit(KEY_A,d.keybit);assert(!boost_match(0,&d));bit(KEY_LEFTMETA,d.keybit);assert(boost_match(0,&d));assert(table_matches(&d));
 d=(struct input_dev){0};bit(EV_ABS,d.evbit);assert(!boost_match(0,&d));bit(ABS_MT_POSITION_X,d.absbit);bit(ABS_MT_POSITION_Y,d.absbit);assert(boost_match(0,&d));assert(table_matches(&d));
 jiffies=1000;boost_event(0,EV_FF,0,1);boost_event(0,EV_KEY,KEY_A,0);assert(!queued);
 boost_event(0,EV_KEY,KEY_A,1);assert(queued==1&&last_input==1000&&rearm==500);
 boost_apply(0);assert(active&&floors[0].value==ceiling[0]&&floors[1].value==ceiling[1]);
 int n=updates;boost_apply(0);assert(updates==n);
 jiffies=1499;boost_release(0);assert(active&&rearm==1);
 boost_event(0,EV_ABS,ABS_MT_POSITION_X,17);jiffies=1500;boost_release(0);assert(active&&rearm==499);
 jiffies=1999;boost_release(0);assert(!active&&!floors[0].value&&!floors[1].value);
 boost_apply(0);assert(!active); /* stale queued work cannot re-boost */
 jiffies=ULONG_MAX-99;boost_event(0,EV_KEY,KEY_A,1);boost_apply(0);assert(active);
 jiffies=399;boost_release(0);assert(active&&rearm==1);jiffies=400;boost_release(0);assert(!active);
 jiffies=10000;boost_event(0,EV_KEY,KEY_A,1);fail_second=1;boost_apply(0);assert(!active&&!floors[0].value&&!floors[1].value);
 boost_apply(0);assert(active);stopping=true;boost_release(0);assert(!active);
 n=queued;boost_event(0,EV_KEY,KEY_A,1);boost_apply(0);assert(queued==n&&!active);
 puts("Actual input filtering, 500ms expiry/retrigger, stale work, jiffies wrap, partial failure and shutdown pass");
}
'''
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    (root / 'test.c').write_text(shim + '\n'.join(functions) + ids + main)
    subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-fsanitize=address,undefined', str(root / 'test.c'), '-o', str(root / 'test')], check=True)
    subprocess.run([str(root / 'test')], check=True)

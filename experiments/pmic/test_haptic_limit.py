#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Sanitize the actual trial's magnitude/duty function over all 16-bit inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kernel-source', type=Path, required=True)
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    pins = json.loads((here / 'HAPTIC_TRIAL.json').read_text())
    original = args.kernel_source / 'drivers/input/misc/max77693-haptic.c'
    patch = here / '0005-g965n-haptic-duty-limit.patch'
    if sha(original) != pins['input_sha256'] or sha(patch) != pins['patch_sha256']:
        raise RuntimeError('Unreviewed source/patch')
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / 'drivers/input/misc/max77693-haptic.c'
        source.parent.mkdir(parents=True)
        source.write_bytes(original.read_bytes())
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', directory,
                        '-i', str(patch.resolve())], check=True, stdout=subprocess.PIPE)
        if sha(source) != pins['output_sha256']:
            raise RuntimeError('Unexpected trial source')
        text = source.read_text()
        start = text.index('static int max77693_haptic_play_effect(')
        function = text[start:text.index('\n}', start) + 2]
        shim = r'''
#include <assert.h>
#include <stdint.h>
typedef uint64_t u64;
#define MAX_MAGNITUDE_SHIFT 16
#define min(a,b) ((a)<(b)?(a):(b))
struct pwm_args { u64 period; };
struct work_struct { int queued; };
struct max77693_haptic { unsigned int magnitude,pwm_duty; void *pwm_dev; struct work_struct work; };
struct input_dev { struct max77693_haptic *data; };
struct ff_effect { union {struct {unsigned short strong_magnitude,weak_magnitude;} rumble;} u; };
static u64 trial_period;
static struct max77693_haptic *input_get_drvdata(struct input_dev *d){return d->data;}
static void pwm_get_args(void *p,struct pwm_args *a){(void)p;a->period=trial_period;}
static void schedule_work(struct work_struct *w){w->queued++;}
'''
        body = r'''
int main(void){
 const u64 periods[]={1,48828,1000000000};
 for(unsigned p=0;p<3;p++)for(unsigned fallback=0;fallback<2;fallback++)for(unsigned value=0;value<65536;value++){
  trial_period=periods[p];
  struct max77693_haptic h={0};struct input_dev d={&h};struct ff_effect f={0};
  f.u.rumble.strong_magnitude=fallback?0:value;
  f.u.rumble.weak_magnitude=fallback?value:65535;
  unsigned expected=fallback?value:(value?value:65535);
  if(expected>32767)expected=32767;
  assert(max77693_haptic_play_effect(&d,0,&f)==0);
  assert(h.magnitude==expected&&h.work.queued==1);
  assert(h.pwm_duty==(unsigned)((trial_period*expected)>>16));
  assert(((trial_period+h.pwm_duty)/2)*4<=trial_period*3+3);
 }
 return 0;
}
'''
        test = root / 'limit.c'
        test.write_text(shim + function + body)
        binary = root / 'limit'
        subprocess.run(['cc', '-O1', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                        str(test), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('Actual haptic function:393216 magnitude/period cases passed with ASan/UBSan')


if __name__ == '__main__':
    main()

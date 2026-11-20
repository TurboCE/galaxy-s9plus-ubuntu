#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the actual original tiled loop with the candidate on native ARM64."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--mesa-source', type=Path, required=True)
a = p.parse_args()
if platform.machine().lower() not in ('aarch64', 'arm64'):
    p.error('Native ARM64 is required')
here = Path(__file__).resolve().parent
pins = json.loads((here / 'TILE32_TRIAL.json').read_text())
original = a.mesa_source / 'src/panfrost/shared/pan_tiling.c'
sha = lambda x: hashlib.sha256(x.read_bytes()).hexdigest()
assert sha(original) == pins['input_sha256'] and sha(here / '0003-panfrost-neon-tile32.patch') == pins['patch_sha256']
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    staged = root / 'src/panfrost/shared/pan_tiling.c'
    staged.parent.mkdir(parents=True)
    staged.write_bytes(original.read_bytes())
    subprocess.run(['patch', '--fuzz=0', '--batch', '-p1', '-d', directory, '-i', str(here / '0003-panfrost-neon-tile32.patch')], check=True)
    assert sha(staged) == pins['output_sha256']
    text, changed = original.read_text(), staged.read_text()
    tables = text[text.index('const uint32_t bit_duplication'):text.index('/* The scheme uses')]
    def function(s, name):
        begin = s.index('\n' + name + '(')
        return s[begin:s.index('\n}', begin) + 2]
    scalar = 'static __attribute__((always_inline)) inline void' + function(text, 'pan_access_tiled_image_aligned')
    vector = 'static void' + function(changed, 'pan_access_tiled_image_32_neon')
    shim = r'''
#include <arm_neon.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <time.h>
#define PIXELS_PER_TILE 256
#define PAN_INTERLEAVE_NONE 0
enum pan_interleave_zs { ZERO };
static inline __attribute__((always_inline)) void pan_access_image_pixel(void *d,void *s,unsigned size,enum pan_interleave_zs i,bool store){assert(size==4&&i==0);if(store)memcpy(d,s,4);else memcpy(s,d,4);}
'''
    body = r'''
static uint32_t rng=1729;
static unsigned next(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
int main(int argc,char **argv){
 (void)argv;unsigned cases=0;
 const unsigned widths[]={0,16,32,48,80,128,256};
 for(unsigned wi=0;wi<7;wi++)for(unsigned h=16;h<=64;h+=16)
 for(unsigned sx=0;sx<=48;sx+=16)for(unsigned sy=0;sy<=32;sy+=16)
 for(unsigned pad=0;pad<2;pad++)for(unsigned skew=0;skew<2;skew++){
  unsigned w=widths[wi],ds=((sx+w)/16+2)*1024+pad*16,ss=w*4+17*pad;
  size_t ts=((sy+h)/16+1)*ds+64,ls=h*ss+64;
  uint8_t *t0=malloc(ts),*t1=malloc(ts),*l0=malloc(ls),*l1=malloc(ls);
  assert(t0&&t1&&l0&&l1);
  for(unsigned store=0;store<2;store++){
   for(size_t n=0;n<ts;n++)t0[n]=next();memcpy(t1,t0,ts);
   for(size_t n=0;n<ls;n++)l0[n]=next();memcpy(l1,l0,ls);
   pan_access_tiled_image_aligned(t0+skew,l0+skew,4,4,2,sx,sy,w,h,ds,ss,0,store);
   pan_access_tiled_image_32_neon(t1+skew,l1+skew,sx,sy,w,h,ds,ss,store);
   assert(!memcmp(t0,t1,ts)&&!memcmp(l0,l1,ls));cases++;
  }
  free(t0);free(t1);free(l0);free(l1);
 }
 printf("PASS %u exact store/load cases including offsets, padding and guards\n",cases);
 if(argc>1){
  unsigned w=1024,h=1024,ds=w*64,ss=w*4;size_t size=w*h*4;
  uint8_t *t=malloc(size),*l=malloc(size);assert(t&&l);memset(l,0x5a,size);
  double start=now();for(int i=0;i<100;i++){pan_access_tiled_image_aligned(t,l,4,4,2,0,0,w,h,ds,ss,0,true);__asm__ volatile("" :: "r"(t) : "memory");}double scalar=now()-start;
  start=now();for(int i=0;i<100;i++){pan_access_tiled_image_32_neon(t,l,0,0,w,h,ds,ss,true);__asm__ volatile("" :: "r"(t) : "memory");}double neon=now()-start;
  printf("BENCH scalar_s=%.6f neon_s=%.6f ratio=%.3f guard=%u\n",scalar,neon,neon/scalar,t[0]);free(t);free(l);
 }
}
'''
    (root / 'test.c').write_text(shim + tables + scalar + vector + body)
    for sanitized in (True, False):
        args = ['cc', '-O3', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation']
        if sanitized:
            args += ['-fsanitize=address,undefined']
        subprocess.run(args + [str(root / 'test.c'), '-o', str(root / 'test')], check=True)
        subprocess.run([str(root / 'test')] + ([] if sanitized else ['benchmark']), check=True)
assert sha(original) == pins['input_sha256']

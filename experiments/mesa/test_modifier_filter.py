#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply the pinned patch to a private copy; compile actual upstream functions.

No Mesa/driver build, installation, device access, or change to the source tree.
The Mesa function retains the notice in LICENSE.pan_resource.MIT.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TARGET = Path('src/gallium/drivers/panfrost/pan_resource.c')
PRISTINE_SHA = '445916b95a284b4f49d76491d60143754976bc7deacabbf4df3bfc56ad7f7eeb'
PATCHED_SHA = 'ba87b87903b99dc75848c4a297fb0cbee5008ef126a0357caa6677068808d605'
PATCH = HERE / '0001-panfrost-check-explicit-modifier-support.patch'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract_function(text, name):
    at = text.index('\n' + name + '(')
    start = text.rfind('static ', 0, at)
    opening = text.index('{', at)
    end = text.index('\n}', opening) + 2
    return text[start:end], start, end


SHIM = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define AFBC UINT64_C(0x0800000000000062)
#define TILED UINT64_C(0x0800000000000001)
#define LINEAR UINT64_C(0)
#define EMULATED UINT64_C(0x0b00000000000001)
#define UNKNOWN UINT64_C(0xfeed)
#define IMPLICIT UINT64_C(0xd3fa017)
#define DRM_FORMAT_MOD_INVALID UINT64_C(0x00ffffffffffffff)
/* Representative entries preserve the upstream native-before-emulated order.
 * This harness tests selection/control flow, not modifier hardware support. */
#define PAN_SUPPORTED_MODIFIERS(n) const uint64_t n[]={AFBC,TILED,LINEAR}
#define PANFROST_EMULATED_MODIFIERS(n) const uint64_t n[]={EMULATED}
struct pipe_screen;
struct pipe_resource { unsigned format; uint64_t modifier; };
struct pipe_screen { bool (*is_dmabuf_modifier_supported)(struct pipe_screen*,uint64_t,unsigned,bool*); };
static bool afbc_allowed,tiled_allowed=true,linear_allowed=true,emulated_allowed=true,allocation_fail;
static unsigned callback_calls,create_calls,implicit_calls;
static struct pipe_resource selected;
static bool supported(struct pipe_screen*s,uint64_t modifier,unsigned format,bool *external_only){
 (void)s;assert(format==101);assert(external_only==NULL);callback_calls++;
 return (modifier==AFBC&&afbc_allowed)||(modifier==TILED&&tiled_allowed)||
        (modifier==LINEAR&&linear_allowed)||(modifier==EMULATED&&emulated_allowed);
}
static bool drm_find_modifier(uint64_t modifier,const uint64_t *list,int count){
 for(int i=0;i<count;i++){if(modifier==list[i])return true;}return false;
}
static struct pipe_resource *panfrost_resource_create_with_modifier(struct pipe_screen*s,
 const struct pipe_resource*t,uint64_t modifier,unsigned plane){
 (void)s;assert(plane==0);create_calls++;if(allocation_fail)return NULL;
 selected=*t;selected.modifier=modifier;return &selected;
}
static struct pipe_resource *panfrost_resource_create(struct pipe_screen*s,const struct pipe_resource*t){
 (void)s;implicit_calls++;selected=*t;selected.modifier=IMPLICIT;return &selected;
}
'''

CASES = r'''
int main(int argc,char **argv){
 assert(argc==2);struct pipe_screen screen={.is_dmabuf_modifier_supported=supported};
 struct pipe_resource request={.format=101};struct pipe_resource *r;const char *test=argv[1];
 if(!strcmp(test,"baseline-bug")){
  uint64_t list[]={AFBC,LINEAR};r=original_create(&screen,&request,list,2);
  assert(r&&r->modifier==AFBC&&!callback_calls);
  r=original_create(&screen,&request,list,1);assert(r&&r->modifier==AFBC&&!callback_calls);
 }else if(!strcmp(test,"noafbc-mixed")){
  uint64_t list[]={AFBC,LINEAR};r=patched_create(&screen,&request,list,2);
  assert(r&&r->modifier==LINEAR&&callback_calls==2&&create_calls==1&&!implicit_calls);
 }else if(!strcmp(test,"noafbc-only")){
  uint64_t list[]={AFBC};r=patched_create(&screen,&request,list,1);
  assert(!r&&callback_calls==1&&!create_calls&&!implicit_calls);
 }else if(!strcmp(test,"afbc-enabled-preference")){
  afbc_allowed=true;uint64_t list[]={LINEAR,AFBC};
  r=original_create(&screen,&request,list,2);assert(r&&r->modifier==AFBC);
  r=patched_create(&screen,&request,list,2);assert(r&&r->modifier==AFBC&&callback_calls==1);
 }else if(!strcmp(test,"linear-unchanged")){
  uint64_t list[]={LINEAR};r=original_create(&screen,&request,list,1);assert(r&&r->modifier==LINEAR);
  r=patched_create(&screen,&request,list,1);assert(r&&r->modifier==LINEAR&&!implicit_calls);
 }else if(!strcmp(test,"emulated-supported")){
  uint64_t list[]={EMULATED};r=original_create(&screen,&request,list,1);assert(r&&r->modifier==EMULATED);
  r=patched_create(&screen,&request,list,1);assert(r&&r->modifier==EMULATED&&callback_calls==1);
 }else if(!strcmp(test,"emulated-rejected")){
  emulated_allowed=false;uint64_t list[]={EMULATED};r=patched_create(&screen,&request,list,1);
  assert(!r&&callback_calls==1&&!create_calls&&!implicit_calls);
 }else if(!strcmp(test,"native-rejected-emulated-selected")){
  uint64_t list[]={AFBC,EMULATED};r=patched_create(&screen,&request,list,2);
  assert(r&&r->modifier==EMULATED&&callback_calls==2&&!implicit_calls);
 }else if(!strcmp(test,"unsupported-and-empty")){
  uint64_t list[]={UNKNOWN};assert(!patched_create(&screen,&request,list,1));
  assert(!patched_create(&screen,&request,NULL,0));assert(!create_calls&&!implicit_calls&&!callback_calls);
 }else if(!strcmp(test,"only-invalid-fallback-unchanged")){
  uint64_t list[]={DRM_FORMAT_MOD_INVALID};r=original_create(&screen,&request,list,1);assert(r&&r->modifier==IMPLICIT);
  r=patched_create(&screen,&request,list,1);assert(r&&r->modifier==IMPLICIT&&implicit_calls==2&&!callback_calls);
 }else if(!strcmp(test,"mixed-invalid-not-implicit")){
  uint64_t list[]={DRM_FORMAT_MOD_INVALID,AFBC};assert(!patched_create(&screen,&request,list,2));assert(!implicit_calls);
 }else if(!strcmp(test,"unknown-plus-supported")){
  uint64_t list[]={UNKNOWN,LINEAR};r=original_create(&screen,&request,list,2);assert(r&&r->modifier==LINEAR);
  r=patched_create(&screen,&request,list,2);assert(r&&r->modifier==LINEAR&&!implicit_calls);
 }else if(!strcmp(test,"allocation-failure-unchanged")){
  afbc_allowed=true;allocation_fail=true;uint64_t list[]={AFBC,LINEAR};
  assert(!original_create(&screen,&request,list,2));assert(!patched_create(&screen,&request,list,2));
  assert(create_calls==2&&callback_calls==1&&!implicit_calls);
 }else assert(!"Unknown test case");
 return 0;
}
'''

SCENARIOS = (
    'baseline-bug', 'noafbc-mixed', 'noafbc-only', 'afbc-enabled-preference',
    'linear-unchanged', 'emulated-supported', 'emulated-rejected',
    'native-rejected-emulated-selected', 'unsupported-and-empty',
    'only-invalid-fallback-unchanged', 'mixed-invalid-not-implicit',
    'unknown-plus-supported', 'allocation-failure-unchanged',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesa-source', type=Path, default=ROOT/'.local/context/mesa-25.2.8')
    parser.add_argument('--cc', default=shutil.which('cc'))
    args = parser.parse_args()
    if not args.cc:
        parser.error('A host C compiler is required')
    original_bytes = (args.mesa_source/TARGET).read_bytes()
    if sha(original_bytes) != PRISTINE_SHA:
        raise SystemExit('Refusing non-pristine/unqualified Mesa source; original left unchanged')
    original_text = original_bytes.decode()
    local = ROOT/'.local';local.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mesa-modifier-regression-', dir=local) as directory:
        work=Path(directory);copy=work/TARGET;copy.parent.mkdir(parents=True)
        copy.write_bytes(original_bytes)
        subprocess.run(['patch','--batch','--forward','--fuzz=0','-p1','-i',str(PATCH)],
                       cwd=work,check=True,capture_output=True,text=True,timeout=15)
        patched_bytes=copy.read_bytes()
        if sha(patched_bytes) != PATCHED_SHA:
            raise AssertionError('Unexpected patched target bytes')
        patched_text=patched_bytes.decode()
        name='panfrost_resource_create_with_modifiers'
        old,start,end=extract_function(original_text,name)
        new,new_start,new_end=extract_function(patched_text,name)
        # Stronger than checking imports alone: every byte outside the sole
        # edited creation function, including notices/defaults/imports, is exact.
        assert original_text[:start]==patched_text[:new_start]
        assert original_text[end:]==patched_text[new_end:]
        assert extract_function(original_text,'panfrost_resource_from_handle')[0]==extract_function(patched_text,'panfrost_resource_from_handle')[0]
        code=SHIM+'\n'+old.replace(name,'original_create',1)+'\n'+new.replace(name,'patched_create',1)+'\n'+CASES
        harness=work/'modifier-filter.c';harness.write_text(code)
        binary=work/'modifier-filter'
        subprocess.run([args.cc,'-std=c11','-Wall','-Wextra','-Werror',str(harness),'-o',str(binary)],
                       check=True,capture_output=True,text=True,timeout=30)
        for scenario in SCENARIOS:
            subprocess.run([str(binary),scenario],check=True,capture_output=True,text=True,timeout=5)
    assert (args.mesa_source/TARGET).read_bytes()==original_bytes
    print(f'PASS: {len(SCENARIOS)} production-function C scenarios; imports/defaults/notices unchanged; pristine source unchanged')
    print(f'patch_sha256={sha(PATCH.read_bytes())}')
    print(f'patched_target_sha256={PATCHED_SHA}')


if __name__=='__main__':
    main()

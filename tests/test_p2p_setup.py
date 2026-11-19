# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib
import importlib.util
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('p2p_setup',ROOT/'scripts/build/g965n-p2p-setup.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
SOURCE=ROOT/'.local/context/wifi-diagnostics-pristine/p2p.c'
STUBS=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;typedef int32_t s32;
#define ETH_ALEN 6
#define BRCMF_C_UP 2
#define BRCMF_C_DOWN 3
#define BRCM_CC_4361_CHIP_ID 4361
struct bus { unsigned int chip; };
struct brcmf_pub { struct bus *bus_if; void *wiphy; };
struct brcmf_if { struct brcmf_pub *drvr; int ifidx; };
static bool target=true;
static int sequence[8],count,failed,logs;
static bool of_machine_is_compatible(const char *s) {assert(!strcmp(s,"samsung,star2lte"));return target;}
#define net_ratelimit() true
static void test_log(unsigned int stage,int ret) {assert(stage<5&&ret<=0);logs++;}
#define wiphy_info(w,fmt,...) do {(void)(w);test_log(__VA_ARGS__);}while(0)
#define bphy_err(d,fmt,...) do {(void)(d);}while(0)
static int operation(int stage) {sequence[count++]=stage;return failed&(1<<stage)?-10-stage:0;}
static int brcmf_fil_cmd_int_set(struct brcmf_if *i,int cmd,int value) {(void)i;assert(value==1);return operation(cmd==BRCMF_C_DOWN?0:2);}
static int brcmf_fil_iovar_int_set(struct brcmf_if *i,const char *name,int value) {(void)i;if(!strcmp(name,"apsta")){assert(value==1);return operation(1);}assert(!strcmp(name,"p2p_disc")&&value==0);return operation(3);}
static int brcmf_fil_iovar_data_set(struct brcmf_if *i,const char *name,u8 *data,int length) {(void)i;(void)data;assert(!strcmp(name,"p2p_da_override")&&length==6);return operation(4);}
'''
CASES=r'''
int main(void) {
 struct bus bus={4361};struct brcmf_pub d={&bus,0};struct brcmf_if i={&d,0};u8 address[6]={0};
 for(int stage=0;stage<5;stage++) {
  failed=1<<stage;count=logs=0;
  assert(brcmf_p2p_set_firmware(&i,address)==-10-stage);
  assert(sequence[0]==0);
  if(stage==1) {assert(count==3&&sequence[2]==2);} /* Restore UP on APSTA rejection. */
  else assert(count==stage+1);
  assert(logs==count);
 }
 failed=(1<<1)|(1<<2);count=0;
 assert(brcmf_p2p_set_firmware(&i,address)==-11&&count==3);
 failed=0;count=0;assert(brcmf_p2p_set_firmware(&i,address)==0&&count==5);
 for(int other=0;other<3;other++) {
  target=other!=0;bus.chip=other==1?4356:4361;i.ifidx=other==2?1:0;
  failed=(1<<0)|(1<<1)|(1<<2)|(1<<3);count=logs=0;
  assert(brcmf_p2p_set_firmware(&i,address)==0&&count==5&&logs==0);
 }
 return 0;
}
'''
class P2pSetupTests(unittest.TestCase):
 def test_actual_c_event_mask_observation_bounds_and_errors(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  stub=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
#define BRCMF_E_IF 54
struct fweh {unsigned int event_mask_len;};
struct pub {struct fweh *fweh;void *wiphy;};
struct brcmf_if {struct pub *drvr;};
static int calls,read_error,actual_bit,seen_ret,seen_bit;
static unsigned int seen_len;
static int brcmf_fil_iovar_data_get(struct brcmf_if *i,const char *name,u8 *mask,unsigned int len) {
 (void)i;assert(!strcmp(name,"event_msgs"));assert(len>6&&len<=256);calls++;
 if(actual_bit)mask[6]=1U<<6;
 return read_error;
}
#define net_ratelimit() true
static void log_result(unsigned int stage,int ret,unsigned int len,unsigned int bit) {
 assert(stage==5);seen_ret=ret;seen_len=len;seen_bit=bit;
}
#define wiphy_info(w,fmt,...) do {(void)(w);log_result(__VA_ARGS__);}while(0)
'''
  cases=r'''
int main(void) {
 struct fweh f={24};struct pub p={&f,0};struct brcmf_if i={&p};
 actual_bit=1;brcmf_g965n_p2p_event_mask(&i);assert(calls==1&&seen_bit==1&&seen_ret==0&&seen_len==24);
 actual_bit=0;brcmf_g965n_p2p_event_mask(&i);assert(calls==2&&seen_bit==0&&seen_ret==0);
 actual_bit=1;read_error=-EIO;brcmf_g965n_p2p_event_mask(&i);assert(calls==3&&seen_bit==0&&seen_ret==-EIO);
 f.event_mask_len=6;brcmf_g965n_p2p_event_mask(&i);assert(calls==3&&seen_ret==-EINVAL);
 f.event_mask_len=257;brcmf_g965n_p2p_event_mask(&i);assert(calls==3&&seen_ret==-EINVAL);
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);(d/'test.c').write_text(stub+p.OBSERVER+cases)
   subprocess.run([cc,'-std=c99','-Wall','-Wextra','-Werror',str(d/'test.c'),'-o',str(d/'test')],check=True)
   subprocess.run([str(d/'test')],check=True)
 def source(self):
  if not SOURCE.exists():self.skipTest('Pinned Linux p2p.c source unavailable')
  data=SOURCE.read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),p.ORIGINAL);return data
 def test_actual_c_required_step_failures_and_up_rollback(self):
  self.source();cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);d.joinpath('test.c').write_text(STUBS+p.HELPERS+p.BODY+CASES)
   subprocess.run([cc,'-std=c99','-Wall','-Wextra','-Werror',str(d/'test.c'),'-o',str(d/'test')],check=True)
   subprocess.run([str(d/'test')],check=True)
 def test_pin_idempotence_drift_refusal_and_caller_propagation(self):
  data=self.source();new=p.transform(data);self.assertEqual(hashlib.sha256(new).hexdigest(),p.PATCHED)
  self.assertTrue(new.startswith(data[:data.index(b'#include')]))
  self.assertIn(b'if (err < 0 && brcmf_g965n_checked_p2p(pri_ifp))\n\t\tgoto fail;',new)
  with tempfile.TemporaryDirectory() as t:
   dest=Path(t)/p.REL;dest.parent.mkdir(parents=True);dest.write_bytes(data)
   p.apply(t);self.assertEqual(dest.read_bytes(),new);p.apply(t)
   dest.write_bytes(b'unreviewed')
   with self.assertRaises(ValueError):p.apply(t)
   self.assertEqual(dest.read_bytes(),b'unreviewed')
if __name__=='__main__':unittest.main()

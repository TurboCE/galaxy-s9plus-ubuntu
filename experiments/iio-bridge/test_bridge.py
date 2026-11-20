#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile real bridge C code against host stubs; no device operations."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
CASES=r'''
#include <assert.h>
#include <limits.h>
#include <string.h>
#include "bridge-core.h"
_Static_assert(sizeof(struct g965n_iio_frame)==48,"UAPI size");
static struct g965n_iio_frame packet(u32 type,u64 seq) {
 struct g965n_iio_frame p={0};p.version=bridge_le32(1);p.size=bridge_le32(48);
 p.seq=bridge_le64(seq);p.type=bridge_le32(type);return p;
}
int main(void) {
 struct g965n_iio_frame p=packet(G965N_IIO_ACCEL,1);struct bridge_decoded d;
 p.flags=bridge_le32(1);p.value[0]=bridge_le32((u32)-32768);p.value[2]=bridge_le32(32767);
 assert(!bridge_decode(&p,48,0,&d));assert(d.value[0]==-32768&&d.value[2]==32767);
 for(unsigned n=0;n<100;n++)if(n!=48)assert(bridge_decode(&p,n,0,&d)==-EMSGSIZE);
 p.version=bridge_le32(2);assert(bridge_decode(&p,48,0,&d)==-EPROTO);p.version=bridge_le32(1);
 p.size=bridge_le32(47);assert(bridge_decode(&p,48,0,&d)==-EMSGSIZE);p.size=bridge_le32(48);
 for(unsigned n=0;n<3;n++){p.reserved[n]=bridge_le32(1);assert(bridge_decode(&p,48,0,&d)==-EINVAL);p.reserved[n]=0;}
 for(u32 f=0;f<16;f++)if(f!=1){p.flags=bridge_le32(f);assert(bridge_decode(&p,48,0,&d)==-EINVAL);}p.flags=bridge_le32(1);
 p.seq=0;assert(bridge_decode(&p,48,0,&d)==-ERANGE);
 p.seq=bridge_le64(2);assert(bridge_decode(&p,48,0,&d)==-ERANGE);
 assert(!bridge_decode(&p,48,1,&d));assert(bridge_decode(&p,48,2,&d)==-ERANGE);
 p.seq=bridge_le64(UINT64_MAX);assert(!bridge_decode(&p,48,1,&d));assert(bridge_decode(&p,48,UINT64_MAX,&d)==-ERANGE);
 for(unsigned n=0;n<3;n++){
  p=packet(G965N_IIO_ACCEL,1);p.flags=bridge_le32(1);p.value[n]=bridge_le32(32768);assert(bridge_decode(&p,48,0,&d)==-ERANGE);
  p.value[n]=bridge_le32((u32)-32769);assert(bridge_decode(&p,48,0,&d)==-ERANGE);
 }
 p=packet(G965N_IIO_LIGHT,1);assert(!bridge_decode(&p,48,0,&d)); /* real darkness0 is valid */
 p.value[0]=bridge_le32((u32)-1);assert(bridge_decode(&p,48,0,&d)==-EINVAL);p.value[0]=bridge_le32(INT_MAX);assert(!bridge_decode(&p,48,0,&d));
 p.value[1]=bridge_le32(1);assert(bridge_decode(&p,48,0,&d)==-EINVAL);p.value[1]=0;p.flags=bridge_le32(1);assert(bridge_decode(&p,48,0,&d)==-EINVAL);
 p=packet(G965N_IIO_HEARTBEAT,1);assert(!bridge_decode(&p,48,0,&d));p.value[2]=bridge_le32(1);assert(bridge_decode(&p,48,0,&d)==-EINVAL);
 p=packet(99,1);assert(bridge_decode(&p,48,0,&d)==-EINVAL);
 p=packet(G965N_IIO_HEADING,1);
 assert(!bridge_decode(&p,48,0,&d)); /* zero is real magnetic north */
 p.value[0]=bridge_le32(359999);assert(!bridge_decode(&p,48,0,&d));
 p.value[0]=bridge_le32(360000);assert(bridge_decode(&p,48,0,&d)==-ERANGE);
 p.value[0]=bridge_le32((u32)-1);assert(!bridge_decode(&p,48,0,&d));
 p.value[0]=bridge_le32((u32)-2);assert(bridge_decode(&p,48,0,&d)==-ERANGE);
 p.value[0]=0;p.value[1]=bridge_le32(1);assert(bridge_decode(&p,48,0,&d)==-EINVAL);
 int identity[9]={1,0,0,0,1,0,0,0,1};assert(bridge_matrix_valid(identity,9));assert(!bridge_matrix_valid(identity,8));
 int malformed[9]={1,0,0,INT_MAX,0,0,0,0,1};assert(!bridge_matrix_valid(malformed,9));malformed[3]=INT_MIN;assert(!bridge_matrix_valid(malformed,9));
 int duplicate[9]={1,0,0,1,0,0,0,0,1};assert(!bridge_matrix_valid(duplicate,9));
 int permutation[6][3]={{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
 for(unsigned a=0;a<6;a++)for(unsigned sign=0;sign<8;sign++) {int m[9]={0};for(unsigned r=0;r<3;r++)m[r*3+permutation[a][r]]=(sign&(1<<r))?-1:1;assert(bridge_matrix_valid(m,9));}
 struct bridge_cache c={.connected=true};s32 value=12345;u64 now=10000000000ULL;
 assert(bridge_read(&c,G965N_IIO_ACCEL,0,now,&value)==-ENODATA&&value==12345);
 assert(bridge_read(&c,G965N_IIO_LIGHT,0,now,&value)==-ENODATA);
 p=packet(G965N_IIO_ACCEL,1);p.flags=bridge_le32(1);p.value[0]=bridge_le32((u32)-42);assert(!bridge_decode(&p,48,c.seq,&d));bridge_update(&c,&d,now);
 assert(!bridge_read(&c,G965N_IIO_ACCEL,0,now,&value)&&value==-42);
 p=packet(G965N_IIO_LIGHT,2);p.value[0]=bridge_le32(123);assert(!bridge_decode(&p,48,c.seq,&d));bridge_update(&c,&d,now);
 assert(!bridge_read(&c,G965N_IIO_LIGHT,0,now,&value)&&value==123);
 now+=G965N_FRESH_NS;assert(!bridge_read(&c,G965N_IIO_ACCEL,0,now,&value));
 now++;assert(bridge_read(&c,G965N_IIO_ACCEL,0,now,&value)==-ENODATA);assert(bridge_read(&c,G965N_IIO_LIGHT,0,now,&value)==-ENODATA);
 p=packet(G965N_IIO_HEARTBEAT,3);assert(!bridge_decode(&p,48,c.seq,&d));bridge_update(&c,&d,now);
 assert(bridge_read(&c,G965N_IIO_ACCEL,0,now,&value)==-ENODATA); /* heartbeat never fabricates accel */
 assert(!bridge_read(&c,G965N_IIO_LIGHT,0,now,&value)&&value==123); /* on-change retained */
 assert(bridge_read(&c,G965N_IIO_LIGHT,0,now-1,&value)==-ENODATA); /* future heartbeat rejected */
 c.connected=false;assert(bridge_read(&c,G965N_IIO_LIGHT,0,now,&value)==-ENODATA);
 assert(bridge_read(&c,99,0,now,&value)==-EINVAL);assert(bridge_read(&c,G965N_IIO_LIGHT,1,now,&value)==-EINVAL);
 return 0;
}
'''
class BridgeCoreTests(unittest.TestCase):
 def test_actual_packet_matrix_and_freshness_c_with_sanitizers(self):
  with tempfile.TemporaryDirectory() as td:
   c=Path(td)/'core.c';binary=Path(td)/'core';c.write_text(CASES)
   subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-fsanitize=address,undefined','-I',str(HERE),str(c),'-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
 def test_actual_module_callbacks_registration_and_teardown_with_sanitizers(self):
  source=(HERE/'g965n-iio-bridge.c').read_text()
  source='\n'.join(line for line in source.splitlines() if not line.startswith('#include <linux/'))
  code=(HERE/'test-module-stubs.h').read_text()+'\n'+source+'\n'+(HERE/'test-module-cases.h').read_text()
  with tempfile.TemporaryDirectory() as td:
   c=Path(td)/'module.c';binary=Path(td)/'module';c.write_text(code)
   subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-fsanitize=address,undefined','-I',str(HERE),str(c),'-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})
if __name__=='__main__':unittest.main()

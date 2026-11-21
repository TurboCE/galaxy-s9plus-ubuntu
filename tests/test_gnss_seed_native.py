# SPDX-License-Identifier: GPL-2.0-only
import subprocess,tempfile,unittest
from pathlib import Path
class NativeSeed(unittest.TestCase):
 def test_actual_c_seed_function(self):
  source=(Path(__file__).parents[1]/'experiments/gnss/hal-probe.c').read_text()
  start=source.index('static void provide_seed(');fn=source[start:source.index('\n}',start)+2]
  shim='''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <string.h>
#include <time.h>
#include <fcntl.h>
#include <assert.h>
struct interface {int (*inject_location)(double,double,float);};
static int hits;
static int inject(double a,double b,float c){assert(a==10&&b==20&&c==25000);hits++;return 0;}
static int fake_clock(int kind,struct timespec *t){(void)kind;t->tv_sec=2000000000;t->tv_nsec=0;return 0;}
#define clock_gettime fake_clock
'''
  main='''
int main(int argc,char **argv){assert(argc==3);int f=open(argv[1],O_RDONLY);assert(f>=0);assert(dup2(f,5)==5);if(f!=5)close(f);struct interface gps={inject};provide_seed(&gps);assert(hits==atoi(argv[2]));close(5);return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);(r/'test.c').write_text(shim+fn+main)
   subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(r/'test.c'),'-o',str(r/'test')],check=True)
   cases=[('v1 10 20 25000 2000000000\n',1),('v1 10 20 25000 1999999700\n',1)]
   cases += [(s,0) for s in ['', 'v1 nan 20 25000 2000000000', 'v1 91 20 25000 2000000000', 'v1 10 181 25000 2000000000','v1 10 20 0 2000000000','v1 10 20 100001 2000000000','v1 10 20 25000 2000000001','v1 10 20 25000 1999999699','v1 10 20 25000 2000000000 junk','v1 10 20 25000 2000000000\x00junk']]
   for data,expected in cases:
    (r/'seed').write_bytes(data.encode());subprocess.run([str(r/'test'),str(r/'seed'),str(expected)],check=True,stdout=subprocess.DEVNULL)
if __name__=='__main__':unittest.main()

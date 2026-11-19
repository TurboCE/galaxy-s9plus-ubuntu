# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual DSM control/command code; prevent restore replay and unsafe reads."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'experiments/audio/snd-zrn-abox.c'


def function(text,name):
    m=re.search(r'(?m)^static [^;{}]*?\b'+name+r'\([^;{}]*\)\s*\{',text)
    if not m:raise ValueError(name)
    end=m.end();depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[m.start():end]


STUB=r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <limits.h>
#include <pthread.h>
typedef uint32_t u32;
#define IPC_ERAP 5
#define REALTIME_EXTRA 0xea
#define DSM_PARAMS 185
#define SNDRV_CTL_ELEM_IFACE_MIXER 2
#define SNDRV_CTL_ELEM_TYPE_INTEGER 2
#define SNDRV_CTL_ELEM_ACCESS_READ 1
#define SNDRV_CTL_ELEM_ACCESS_READWRITE 3
#define READ_ONCE(x) (x)
struct snd_kcontrol {int unused;};
struct snd_ctl_elem_info {int type,count;struct {struct {long min,max;} integer;} value;};
struct snd_ctl_elem_value {struct {struct {long value[1];} integer;} value;};
struct snd_kcontrol_new {
 int iface;const char *name;unsigned int access;
 int (*info)(struct snd_kcontrol *,struct snd_ctl_elem_info *);
 int (*get)(struct snd_kcontrol *,struct snd_ctl_elem_value *);
 int (*put)(struct snd_kcontrol *,struct snd_ctl_elem_value *);
};
struct kernel_param {int unused;};
static bool booted=true,suspending,dsp_fault;
static pthread_mutex_t stream_lock=PTHREAD_MUTEX_INITIALIZER;
#define mutex_lock(p) assert(pthread_mutex_lock(p)==0)
#define mutex_unlock(p) assert(pthread_mutex_unlock(p)==0)
static int kstrtouint(const char *text,unsigned int base,unsigned int *value) {
 char *end;unsigned long n;errno=0;
 if(*text=='-')return -EINVAL;
 n=strtoul(text,&end,base);
 if(end==text||*end)return -EINVAL;
 if(errno||n>UINT_MAX)return -ERANGE;
 *value=n;return 0;
}
static int sends,ipc_error;static u32 offset_sent;
static int ipc_send(const u32 *m,int n) {
 assert(pthread_mutex_trylock(&stream_lock)==EBUSY);
 assert(n==6&&m[0]==5&&m[2]==0xea&&m[3]==0&&m[5]==4);
 sends++;offset_sent=m[4];return ipc_error;
}
'''
CASES=r'''
int main(void) {
 struct snd_ctl_elem_value value={0};
 assert(dsmr_control.access==SNDRV_CTL_ELEM_ACCESS_READ&&!dsmr_control.put);
 assert(dsmr_control.get(0,&value)==0&&value.value.integer.value[0]==0&&sends==0);
 assert(dsm_read_cmd_set("0",0)==0&&sends==1&&offset_sent==0);
 assert(dsm_read_cmd_set("366",0)==0&&sends==2&&offset_sent==366);
 for(int i=0;i<4;i++) {
  const char *bad[]={"-1","367","369","4294967296"};
  assert(dsm_read_cmd_set(bad[i],0)<0&&sends==2);
 }
 assert(dsm_read_cmd_set("bad",0)==-EINVAL&&sends==2);
 booted=false;assert(dsm_read_cmd_set("18",0)==-EIO&&sends==2);booted=true;
 suspending=true;assert(dsm_read_cmd_set("18",0)==-EIO&&sends==2);suspending=false;
 dsp_fault=true;assert(dsm_read_cmd_set("18",0)==-EIO&&sends==2);dsp_fault=false;
 ipc_error=-ETIMEDOUT;assert(dsm_read_cmd_set("18",0)==-ETIMEDOUT&&sends==3);
 assert(pthread_mutex_trylock(&stream_lock)==0);pthread_mutex_unlock(&stream_lock);
 return 0;
}
'''


class DsmCommandTests(unittest.TestCase):
    def test_actual_read_only_legacy_control_and_explicit_checked_command(self):
        cc=shutil.which('cc')
        if not cc:self.skipTest('C compiler unavailable')
        text=SOURCE.read_text()
        m=re.search(r'static const struct snd_kcontrol_new dsmr_control = \{.*?\n\};',text,re.S)
        self.assertIsNotNone(m)
        body='\n'.join(function(text,n) for n in ['dsm_read','dsmr_info','dsmr_get','dsm_read_cmd_set'])+'\n'+m[0]
        self.assertIn('module_param_cb(dsm_read_cmd, &dsm_read_cmd_ops, NULL, 0200)',text)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.c').write_text(STUB+body+CASES)
            subprocess.run([cc,'-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-pthread',str(p/'test.c'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)


if __name__=='__main__':unittest.main()

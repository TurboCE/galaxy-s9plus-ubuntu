# SPDX-License-Identifier: GPL-2.0-only
"""Run the actual transaction helper against injected transport failures."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PanelAorTests(unittest.TestCase):
    def test_actual_ramp_worker_sleep_retarget_and_transport_failure(self):
        compiler=shutil.which('cc')
        if not compiler:self.skipTest('C compiler unavailable')
        source=(ROOT/'src/gpu/drm/s9p/s9p-decon.c').read_text()
        worker=source.split('static void s9p_backlight_ramp(',1)[1].split('static void s9p_backlight_cancel(',1)[0]
        code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
#include "panel-aor.h"
struct work_struct {int unused;};
struct delayed_work {struct work_struct work;};
struct s9p_decon {int panel_lock;bool panel_awake,aor_valid;int aor_target,aor_applied;struct delayed_work aor_work;};
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define to_delayed_work(p) container_of(p,struct delayed_work,work)
#define mutex_lock(p) ((void)(p))
#define mutex_unlock(p) ((void)(p))
#define system_wq 0
#define msecs_to_jiffies(p) (p)
static int queued,writes,failed;
static void mod_delayed_work(int q,struct delayed_work *w,int delay) {(void)q;(void)w;assert(delay==40);queued++;}
static int send(void *p,const unsigned char *d,unsigned int n) {(void)p;(void)d;(void)n;return failed?-ETIMEDOUT:0;}
static int s9p_brightness_locked(struct s9p_decon *p,int n) {
 int r=s9p_aor_apply(p,n,send);writes++;p->aor_valid=!r;if(!r)p->aor_applied=n;return r;
}
'''+ 'static void s9p_backlight_ramp('+worker+r'''
int main(void) {
 struct s9p_decon p={.panel_awake=true,.aor_valid=true,.aor_target=401,.aor_applied=1};
 s9p_backlight_ramp(&p.aor_work.work);assert(writes==1&&p.aor_applied==5&&queued==1);
 p.aor_target=2;queued=0;s9p_backlight_ramp(&p.aor_work.work);assert(p.aor_applied==2&&queued==0);
 p.panel_awake=false;p.aor_target=401;writes=0;s9p_backlight_ramp(&p.aor_work.work);assert(writes==0&&queued==0);
 p.panel_awake=true;p.aor_target=0;s9p_backlight_ramp(&p.aor_work.work);assert(writes==0&&queued==0);
 p.aor_target=401;failed=1;s9p_backlight_ramp(&p.aor_work.work);assert(writes==1&&!p.aor_valid&&queued==0&&p.aor_applied==2);
 s9p_backlight_ramp(&p.aor_work.work);assert(writes==1&&queued==0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            p=Path(temporary);(p/'ramp.c').write_text(code)
            subprocess.run([compiler,'-std=c99','-Wall','-Wextra','-Werror','-I',str(ROOT/'src/gpu/drm/s9p'),str(p/'ramp.c'),'-o',str(p/'ramp')],check=True)
            subprocess.run([str(p/'ramp')],check=True)
    def test_actual_c_sequence_closes_key_at_each_failure_and_preserves_error(self):
        compiler = shutil.which('cc')
        if not compiler:
            self.skipTest('C compiler unavailable')
        code = r'''
#include <errno.h>
#include <assert.h>
#include "panel-aor.h"
static unsigned char messages[8][3];
static unsigned int lengths[8], count, fail_at;
static int send(void *unused, const unsigned char *data, unsigned int length) {
 unsigned int index = count++;
 (void)unused;
 lengths[index] = length;
 for (unsigned int i=0; i<length; i++) messages[index][i] = data[i];
 return index == fail_at ? -ETIMEDOUT : 0;
}
int main(void) {
 for (unsigned int level=1;level<=S9P_AOR_MAX;level++) {
  count=0; fail_at=100;
  assert(s9p_aor_apply(0,level,send)==0 && count==4);
  assert(messages[0][0]==0xf0 && messages[0][1]==0x5a);
  assert(messages[1][0]==0xb1 && lengths[1]==3);
  assert(messages[2][0]==0xf7 && messages[2][1]==3);
  assert(messages[3][0]==0xf0 && messages[3][1]==0xa5);
  if(level>1) assert(s9p_aor_values[level-1]<s9p_aor_values[level-2]);
 }
 for (fail_at=0;fail_at<4;fail_at++) {
  count=0;
  assert(s9p_aor_apply(0,8,send)==-ETIMEDOUT);
  assert(messages[count-1][0]==0xf0 && messages[count-1][1]==0xa5);
 }
 for(unsigned int start=1;start<=S9P_AOR_MAX;start+=7) {
  for(unsigned int target=1;target<=S9P_AOR_MAX;target+=11) {
   unsigned int cur=start,steps=0;
   while(cur!=target) {
    unsigned int next=s9p_aor_next(cur,target);
    assert(next>=1&&next<=S9P_AOR_MAX);
    assert((next>cur?next-cur:cur-next)<=S9P_AOR_RAMP_STEP);
    assert(cur<target?(next>cur&&next<=target):(next<cur&&next>=target));
    cur=next;assert(++steps<=S9P_AOR_MAX);
   }
  }
 }
 count=0;
 assert(s9p_aor_apply(0,0,send)==-EINVAL);
 assert(s9p_aor_apply(0,S9P_AOR_MAX+1,send)==-EINVAL && count==0);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path/'trial.c').write_text(code)
            subprocess.run([compiler,'-std=c99','-Wall','-Wextra','-Werror',
                '-I',str(ROOT/'src/gpu/drm/s9p'),str(path/'trial.c'),'-o',str(path/'trial')],check=True)
            subprocess.run([str(path/'trial')],check=True)

if __name__ == '__main__':
    unittest.main()

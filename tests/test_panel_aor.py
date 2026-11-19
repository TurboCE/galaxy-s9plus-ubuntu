# SPDX-License-Identifier: GPL-2.0-only
"""Run the actual transaction helper against injected transport failures."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PanelAorTests(unittest.TestCase):
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
 count=0;
 assert(s9p_aor_apply(0,0,send)==-EINVAL);
 assert(s9p_aor_apply(0,17,send)==-EINVAL && count==0);
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

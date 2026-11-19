# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class SsiAckTests(unittest.TestCase):
 def test_actual_ack_helper_rejects_false_success_and_preserves_known_progress(self):
  cc=shutil.which('cc')
  if not cc:self.skipTest('C compiler unavailable')
  code=r'''
#include <errno.h>
#include <assert.h>
#include "ssi-ack.h"
int main(void) {
 struct ssi_ack_state a={36,0};
 for (int i=0;i<3;i++) assert(ssi_ack_accept(&a,0)==0);
 assert(a.acknowledged==0 && ssi_ack_result(&a,0)==-ETIMEDOUT);
 assert(ssi_ack_accept(&a,12)==0);
 assert(a.acknowledged==12 && a.remaining==24);
 assert(ssi_ack_result(&a,-EIO)==-EIO);
 assert(ssi_ack_accept(&a,25)==-EPROTO);
 assert(a.acknowledged==12 && a.remaining==24);
 assert(ssi_ack_accept(&a,8)==0 && ssi_ack_accept(&a,16)==0);
 assert(a.acknowledged==36 && a.remaining==0);
 assert(ssi_ack_result(&a,0)==0);
 assert(ssi_ack_result(&a,-EPROTO)==-EPROTO);
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as temporary:
   p=Path(temporary);p.joinpath('test.c').write_text(code)
   subprocess.run([cc,'-std=c99','-Wall','-Wextra','-Werror','-I',str(ROOT/'experiments/sensors'),str(p/'test.c'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()

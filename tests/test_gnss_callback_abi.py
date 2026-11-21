# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the own-device callback read that previously escaped legacy prefix."""
import subprocess,tempfile,unittest
from pathlib import Path
class CallbackABI(unittest.TestCase):
 def test_vendor_request_slot_calls_valid_persistent_handler(self):
  source=(Path(__file__).parents[1]/'experiments/gnss/hal-probe.c').read_text()
  a=source.index('struct callbacks {');layout=source[a:source.index('\n};',a)+3]
  a=source.index('static void request_location(');handler=source[a:source.index('\n}',a)+2]
  program='''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <pthread.h>
#include <stdatomic.h>
#include <string.h>
#include <assert.h>
static atomic_uint location_requests;
'''+layout+'\n'+handler+'''
int main(void) {
 static struct callbacks cb={.size=sizeof(cb),.request_location=request_location};
 _Static_assert(offsetof(struct callbacks,request_location)==96,"vendor LP64 slot");
 void (*request)(bool,bool);
 memcpy(&request,(char *)&cb+96,sizeof(request));
 request(false,false);request(true,true);
 assert(atomic_load(&location_requests)==2);
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(program)
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()

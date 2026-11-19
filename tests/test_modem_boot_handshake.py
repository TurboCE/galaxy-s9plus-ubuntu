# SPDX-License-Identifier: GPL-2.0-only
"""Run actual driver handshake functions against reset/order instrumentation."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def function(source, name):
    import re
    match=re.search(r'static (?:bool|void|int) '+name+r'\([^;]*?\)\n\{',source)
    if not match:raise AssertionError('Driver function missing: '+name)
    begin=match.start();at=source.index('{',match.start());depth=1;end=at+1
    while depth:
        if source[end]=='{':depth+=1
        elif source[end]=='}':depth-=1
        end+=1
    return source[begin:end]


HARNESS=r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#define SIPC5_CH_ID_FMT_0 1
#define SIPC5_CH_ID_FMT_9 10
#define SIPC5_CH_ID_RFS_0 11
#define SIPC5_CH_ID_RFS_9 20
#define LINK_STATE_OFFLINE 0
#define LINK_STATE_IPC 1
#define CMD_INIT_END 2
#define CRASH_REASON_CP_RSV_0 0
#define MODEM_EVENT_ONLINE 1
#define CMD_RGN_OFFSET 0
#define CMD_RGN_SIZE 16
#define MIF_INIT_TIMEOUT 1500
#define STATE_ONLINE 2
#define mif_err(...) ((void)0)
#define mif_info(...) ((void)0)
#define cmd2int(x) (x)
#define mc_state(x) "stub"
#define atomic_read(x) (*(x))
#define atomic_set(x,v) do { assert(lock_depth==1);*(x)=(v); } while(0)
static int lock_depth, writes, sends, resets, reset_error, memory_ready, completed;
static int cp_watchdog, cp_failure;
#define spin_lock_irqsave(p,f) do { assert(lock_depth==0);lock_depth=1;(f)=0; } while(0)
#define spin_unlock_irqrestore(p,f) do { assert(lock_depth==1);lock_depth=0;(void)(f); } while(0)
#define list_for_each_entry(iod, head, member) for ((iod) = *(head); (iod); (iod) = 0)
struct io_device { int id,opened; const char *name; void (*modem_state_changed)(struct io_device *, int); };
struct modem_ctl {
    const char *name;
    int init_cmpl, irq_cp_wdt, irq_cp_fail;
    struct io_device *modem_state_notify_list;
};
struct mem_link_device;
struct link_device { struct modem_ctl *mc; const char *name; struct mem_link_device *mld; int sbd_ipc; };
struct sbd_link_device { int unused; };
struct mem_link_device { struct link_device link_dev;int state,cp_boot_done,state_lock,tx_timer,sbd_tx_timer,iosm; char *base;struct sbd_link_device sbd_link_dev; };
static struct io_device fmt={1,0,"fmt"},rfs={11,0,"rfs"};
static struct mem_link_device *to_mem_link_device(struct link_device *ld){return ld->mld;}
static struct io_device *link_get_iod_with_channel(struct link_device *ld,int id){(void)ld;return id==1?&fmt:id==11?&rfs:0;}
static void write_clk_table_to_shmem(struct mem_link_device *m){assert(lock_depth==1);assert(m->state==LINK_STATE_IPC);assert(memory_ready);writes++;}
static void send_ipc_irq(struct mem_link_device *m,int command){(void)m;assert(lock_depth==1);assert(memory_ready);assert(command==CMD_INIT_END);assert(writes>sends);sends++;}
static int shmem_reset_ipc_link(struct mem_link_device *m){(void)m;assert(lock_depth==1);resets++;if(reset_error)return reset_error;memory_ready=1;return 0;}
static void mcu_ipc_reg_dump(int n){(void)n;}
static void shmem_forced_cp_crash(struct mem_link_device *m,int why,const char *text){(void)m;(void)why;(void)text;assert(0);}
static void reinit_completion(int *p){assert(lock_depth==1);*p=0;}
static void complete_all(int *p){assert(lock_depth==1);*p=1;completed++;}
static unsigned long wait_for_completion_timeout(int *p, unsigned long timeout)
{assert(lock_depth==0 && timeout==MIF_INIT_TIMEOUT);return *p;}
static void mif_enable_irq(int *irq){assert(!*irq);*irq=1;cp_watchdog++;}
static void mif_disable_irq(int *irq){assert(*irq);*irq=0;cp_failure++;}
static void modem_notify_event(int n){(void)n;}
static void cancel_tx_timer(struct mem_link_device *m,int *t){(void)m;(void)t;}
static void cancel_datalloc_timer(struct mem_link_device *m){(void)m;}
static int smapper_active(struct sbd_link_device *s){(void)s;return 0;}
static void purge_txq(struct mem_link_device *m){(void)m;}
'''
MAIN=r'''
static void user_open(struct mem_link_device *m,struct io_device *iod){iod->opened++;assert(shmem_init_comm(&m->link_dev,iod)==0);assert(lock_depth==0);}
static struct mem_link_device fresh(struct modem_ctl *mc){struct mem_link_device m={0};m.link_dev.mc=mc;m.link_dev.name="link";fmt.opened=rfs.opened=0;writes=sends=resets=reset_error=memory_ready=completed=lock_depth=0;return m;}
int main(void){
 struct modem_ctl mc={"cp",0};
 for(int order=0;order<2;order++){
  struct mem_link_device m=fresh(&mc);m.link_dev.mld=&m;m.link_dev.sbd_ipc=order;
  struct io_device *first=order?&rfs:&fmt,*second=order?&fmt:&rfs;
  /* Both endpoints opened before CP boot: absolutely no early shared writes. */
  user_open(&m,first);user_open(&m,second);assert(writes==0&&sends==0&&m.cp_boot_done==0);
  shmem_boot_on(&m.link_dev,first);assert(m.state==0&&m.cp_boot_done==0);
  cmd_phone_start_handler(&m);assert(resets==1&&writes==1&&sends==1&&m.cp_boot_done==1&&completed==1);
  user_open(&m,first);assert(writes==1&&sends==1);
  /* Original CP_START retransmission behavior is retained. */
  cmd_phone_start_handler(&m);assert(sends==2&&writes==2);
  /* Another boot clears completion coherently and rewrites after reset. */
  shmem_boot_on(&m.link_dev,first);memory_ready=0;assert(m.state==0&&m.cp_boot_done==0);
  cmd_phone_start_handler(&m);assert(resets==2&&sends==3&&writes==3);
 }
 for(int order=0;order<2;order++){
  struct mem_link_device m=fresh(&mc);m.link_dev.mld=&m;m.link_dev.sbd_ipc=order;
  struct io_device *first=order?&rfs:&fmt,*second=order?&fmt:&rfs;
  /* CP starts first; neither a lone endpoint nor another reference completes. */
  cmd_phone_start_handler(&m);assert(m.state==1&&resets==1&&writes==0&&sends==0&&m.cp_boot_done==0);
  user_open(&m,first);user_open(&m,first);assert(sends==0);
  user_open(&m,second);assert(writes==1&&sends==1&&m.cp_boot_done==1);
  user_open(&m,second);assert(sends==1);
 }
 { struct mem_link_device m=fresh(&mc);m.link_dev.mld=&m;
   user_open(&m,&fmt);cmd_phone_start_handler(&m);assert(sends==0&&m.state==1);
   user_open(&m,&rfs);assert(sends==1&&writes==1); }
 { struct mem_link_device m=fresh(&mc);m.link_dev.mld=&m;
   user_open(&m,&fmt);user_open(&m,&rfs);reset_error=-EIO;
   cmd_phone_start_handler(&m);assert(m.state==0&&sends==0&&writes==0&&m.cp_boot_done==0&&lock_depth==0);
 }
 { struct mem_link_device m=fresh(&mc);m.link_dev.mld=&m;
   mc.init_cmpl=1;mc.irq_cp_fail=1;
   shmem_boot_on(&m.link_dev,&fmt);
   assert(!mc.init_cmpl);
   assert(ss310ap_boot_off(&mc)==-EAGAIN && !cp_watchdog && cp_failure==1);
   mc.irq_cp_fail=1;
   shmem_boot_on(&m.link_dev,&fmt);
   cmd_phone_start_handler(&m);
   assert(mc.init_cmpl && completed==1);
   assert(ss310ap_boot_off(&mc)==0 && cp_watchdog==1 && cp_failure==2);
   assert(mc.init_cmpl && mc.irq_cp_wdt && !mc.irq_cp_fail);
   shmem_boot_on(&m.link_dev,&fmt);
   assert(!mc.init_cmpl);
 }
 return 0;
}
'''


class BootHandshakeTests(unittest.TestCase):
    def test_real_functions_handle_early_late_reversed_partial_and_failed_boot(self):
        compiler=shutil.which('cc')
        self.assertIsNotNone(compiler,'C compiler required for actual driver-function test')
        source=(ROOT/'experiments/modem/link_device_shmem.c').read_text()
        functions='\n'.join(function(source,n) for n in ('rild_ready','cmd_phone_start_handler','shmem_init_comm','shmem_boot_on'))
        controller=(ROOT/'experiments/modem/modem_ctrl_ss310ap.c').read_text()
        functions += '\n' + function(controller, 'ss310ap_boot_off')
        with tempfile.TemporaryDirectory() as name:
            c=Path(name)/'handshake.c';exe=Path(name)/'handshake';c.write_text(HARNESS+functions+MAIN)
            subprocess.run([compiler,'-std=gnu11','-Werror','-Wno-unused-function','-Wno-unused-variable',str(c),'-o',str(exe)],check=True,capture_output=True,text=True)
            subprocess.run([str(exe)],check=True,capture_output=True,text=True)


if __name__=='__main__':unittest.main()

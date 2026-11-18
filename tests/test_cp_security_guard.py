# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual production C with faultable PMU/SMC and real pthread locks."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def function(path,name):
    text=(ROOT/path).read_text();start=text.index(name+'(')
    start=text.rfind('\n',0,start)+1
    opening=text.index('{',start)
    end=text.index('\n}',opening)+2
    return text[start:end]



SHIM=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
#include <unistd.h>
typedef uint32_t u32;
#define U32_MAX UINT32_MAX
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define CONFIG_CP_PMUCAL 1
#define CONFIG_CP_SECURE_BOOT 1
#define CONFIG_SOC_EXYNOS9810 1
#define IS_ENABLED(x) (x)
#define __iomem
#define __user
#define mif_err(...) ((void)0)
#define mif_info(...) ((void)0)
#define pr_info(...) ((void)0)
#define SMC_ID 0x82000700ul
#define SMC_ID_CLK 0x82001011ul
#define SSS_CLK_ENABLE 0
#define SSS_CLK_DISABLE 1
#define CP_BOOT_REQ_CP_RAM_LOGGING 5
#define MCU_CP 0
#define CP_POWER_OFF 0
#define STATE_OFFLINE 0
#define STATE_ONLINE 4
#define STATE_CRASH_EXIT 2
#define MODEM_EVENT_RESET 1
#define AP2CP_CFG_ADDR 0x14820000
#define AP2CP_CFG_DONE 1
#define SZ_64 64
#define READ_CTRL 3
#define WRITE_CTRL 4
#define CP_CTRL_S 0x34
#define CP_CTRL_NS 0x30
#define DEFINE_MUTEX(x) pthread_mutex_t x=PTHREAD_MUTEX_INITIALIZER
#define mutex_lock(x) assert(pthread_mutex_lock(x)==0)
#define mutex_unlock(x) assert(pthread_mutex_unlock(x)==0)
#define READ_ONCE(x) __atomic_load_n(&(x),__ATOMIC_SEQ_CST)
#define WRITE_ONCE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_SEQ_CST)
typedef struct { atomic_int value; } atomic_t;
#define ATOMIC_INIT(x) { ATOMIC_VAR_INIT(x) }
static bool inject_after_epoch_read;static atomic_t *inject_target;
static int mock_atomic_read(atomic_t *p){int value=atomic_load(&p->value);
 if(inject_after_epoch_read&&p==inject_target){inject_after_epoch_read=false;atomic_fetch_add(&p->value,1);}return value;}
#define atomic_read(x) mock_atomic_read(x)
#define atomic_set(x,v) atomic_store(&(x)->value,(v))
#define atomic_inc(x) atomic_fetch_add(&(x)->value,1)
struct modem_ctl { int int_cp_wakeup,phone_state,off_cmpl; void *dev,*bootd;
 int mbx_cp_status,sbi_lte_active_mask,sbi_lte_active_pos,sbi_cp_status_mask,sbi_cp_status_pos;
 int mbx_ap_status,sbi_pda_active_mask,sbi_pda_active_pos,sbi_ap_status_mask,sbi_ap_status_pos; };
struct link_device { const char *name; int (*dump_start)(struct link_device*,void*); };
struct io_device { atomic_t opened; void (*modem_state_changed)(struct io_device*,int); };
struct modem_sec_req { u32 mode,size_boot,size_main; };
#define list_for_each_entry(pos,head,member) for(pos=NULL;pos!=NULL;pos=NULL)
static int cp_init_done;static bool cp_security_failed;static DEFINE_MUTEX(cp_security_lock);
static atomic_t cp_security_irq_epoch=ATOMIC_INIT(0),cp_expected_reset=ATOMIC_INIT(0);
static int cp_accepted_irq_epoch,cp_power_irq_epoch;
static atomic_int security_calls,clock_on,clock_off,ctrl_writes;
static int statuses[16],status_count=1,status_index,init_result,assert_result,release_result;
static int security_result,clock_on_result,clock_off_result,control_result;
static int init_calls,mailbox_result,manual_result,map_failure,map_writes,sw_resets,dump_result;
static bool memory_map=true,irq_in_init,irq_in_assert,offline_in_assert,offline_in_wait,fatal_in_wait;
static unsigned long last_mode,last_p2,last_p3;
static int events[64],event_count;
static atomic_int hold_assert,assert_entered,release_assert;
static u32 fake_reg;
static int record(int v){events[event_count++]=v;return v;}
static int cal_cp_status(void){record(1);int i=status_index++;return statuses[i<status_count?i:status_count-1];}
void g965n_cp_security_irq_failure(void);void g965n_cp_security_offline_irq(void);
static int cal_cp_init(void){record(3);init_calls++;if(irq_in_init)g965n_cp_security_irq_failure();return init_result;}
static int cal_cp_reset_assert(void){record(6);if(irq_in_assert)g965n_cp_security_irq_failure();if(offline_in_assert)g965n_cp_security_offline_irq();
 if(atomic_load(&hold_assert)){atomic_store(&assert_entered,1);while(!atomic_load(&release_assert))usleep(100);}return assert_result;}
static int cal_cp_reset_release(void){record(7);return release_result;}
static void cal_cp_enable_dump_pc_no_pg(void){}
static int exynos_smc(unsigned long id,unsigned long a,unsigned long b,unsigned long c){
 if(id==SMC_ID_CLK){if(a==SSS_CLK_ENABLE){record(2);clock_on++;return clock_on_result;}record(5);clock_off++;return clock_off_result;}
 if(a==WRITE_CTRL){ctrl_writes++;return control_result;}
 if(a==READ_CTRL)return control_result;
 record(4);security_calls++;last_mode=a;last_p2=b;last_p3=c;return security_result;
}
static int shm_get_use_cp_memory_map_flag(void){return memory_map;}
static unsigned long shm_get_phys_base(void){return 0xf0000000ul;}
static void *shm_get_ipc_region(void){return NULL;}
static int copy_from_user(void *dst,const void *src,size_t n){if(!src)return 1;memcpy(dst,src,n);return 0;}
static int shm_get_security_param2(unsigned long mode,u32 boot,unsigned long *p){if(mode>2)return -EINVAL;*p=mode==2?0:boot;return 0;}
static int shm_get_security_param3(unsigned long mode,u32 main,unsigned long *p){if(mode>2)return -EINVAL;*p=mode==2?0:main;return 0;}
static void mbox_set_interrupt(int a,int b){(void)a;(void)b;}
static void mbox_sw_reset(int a){(void)a;sw_resets++;}
static void msleep(int ms){(void)ms;}
static int mb_extract(int a,int b,int c,int d){(void)a;(void)b;(void)c;(void)d;return 0;}
#define mbox_extract_value mb_extract
static void mbox_update_value(int a,int b,int c,int d,int e){(void)a;(void)b;(void)c;(void)d;(void)e;}
static void modem_notify_event(int a){(void)a;}
static void mif_set_snapshot(bool a){(void)a;}
static int init_mailbox_regs(struct modem_ctl *m){(void)m;return mailbox_result;}
static void *devm_ioremap(void *d,unsigned long a,int n){(void)d;(void)a;(void)n;return map_failure?NULL:&fake_reg;}
static u32 __raw_readl(void *p){return *(u32*)p;}
static void __raw_writel(u32 v,void *p){map_writes++;*(u32*)p=v;}
static void devm_iounmap(void*d,void*p){(void)d;(void)p;}
static int change_cp_pmu_manual_reset(void){return manual_result;}
static unsigned long msecs_to_jiffies(unsigned long n){return n;}
static void reinit_completion(int *p){(void)p;}
static unsigned long wait_for_completion_timeout(int*p,unsigned long t){(void)p;(void)t;
 if(offline_in_wait)g965n_cp_security_offline_irq();if(fatal_in_wait)g965n_cp_security_irq_failure();return 1;}
static int mock_dump_start(struct link_device*l,void*i){(void)l;(void)i;return dump_result;}
static struct link_device fixture_link={.name="fixture",.dump_start=mock_dump_start};
static struct link_device *get_current_link(void *p){(void)p;return &fixture_link;}
'''

HARNESS=r'''
static void clear(void){cp_init_done=0;cp_security_failed=false;atomic_set(&cp_security_irq_epoch,0);atomic_set(&cp_expected_reset,0);
 cp_accepted_irq_epoch=cp_power_irq_epoch=0;inject_after_epoch_read=false;inject_target=NULL;security_calls=clock_on=clock_off=ctrl_writes=0;
 status_count=1;status_index=0;statuses[0]=1;init_result=assert_result=release_result=0;
 security_result=clock_on_result=clock_off_result=control_result=0;init_calls=0;event_count=0;
 mailbox_result=manual_result=map_failure=map_writes=sw_resets=dump_result=0;
 irq_in_init=irq_in_assert=offline_in_assert=offline_in_wait=fatal_in_wait=false;atomic_store(&hold_assert,0);atomic_store(&assert_entered,0);atomic_store(&release_assert,0);}
static void balanced(void){assert(pthread_mutex_trylock(&cp_security_lock)==0);pthread_mutex_unlock(&cp_security_lock);assert(!atomic_read(&cp_expected_reset));}
static void *off_thread(void*p){int r=ss310ap_off(p);return (void*)(intptr_t)r;}
static void *security_thread(void*p){(void)p;int r=g965n_cp_security_request(0,0x1e40,0x24075c0);return (void*)(intptr_t)r;}
int main(int argc,char **argv){assert(argc==2);clear();const char *test=argv[1];struct modem_ctl mc={.phone_state=STATE_ONLINE};
 if(!strcmp(test,"pmu-init-fail")){statuses[0]=0;init_result=-ETIMEDOUT;assert(g965n_cp_security_request(2,0,0)==-ETIMEDOUT);
  assert(!security_calls&&clock_on==1&&clock_off==1&&!cp_init_done&&cp_security_failed);
  assert(g965n_cp_security_request(0,1,2)==-EIO);assert(!security_calls&&clock_on==1);}
 else if(!strcmp(test,"status-fail")){statuses[0]=-EIO;assert(g965n_cp_security_request(0,1,2)==-EIO);assert(!security_calls&&!clock_on&&!clock_off);}
 else if(!strcmp(test,"post-init-unready")){statuses[0]=0;assert(g965n_cp_security_request(0,1,2)==-EIO);assert(init_calls==1&&!security_calls&&!cp_init_done&&clock_on==clock_off);}
 else if(!strcmp(test,"cold-success")){statuses[0]=0;statuses[1]=1;status_count=2;assert(g965n_cp_security_request(0,0x1e40,0x24075c0)==0);
  assert(cp_init_done&&!cp_security_failed&&security_calls==1&&clock_on==clock_off);
  int expected[]={1,2,3,1,4,5};assert(event_count==6&&!memcmp(events,expected,sizeof(expected)));
  assert(last_mode==0xf0000000ul&&last_p2==0x1e40&&last_p3==0x24075c0);}
 else if(!strcmp(test,"mode2-positive-abi")){int values[]={0,1,11,12,20,INT_MAX};for(unsigned int i=0;i<sizeof(values)/sizeof(values[0]);i++){clear();security_result=values[i];assert(g965n_cp_security_request(2,0,0)==values[i]);assert(!cp_security_failed);}clear();security_result=11;assert(g965n_cp_security_request(2,0,0)==11);assert(!cp_security_failed);
  security_result=0;assert(g965n_cp_security_request(0,0x1e40,0x24075c0)==0);assert(security_calls==2&&clock_on==2&&clock_off==2);}
 else if(!strcmp(test,"terminal-error")){security_result=14;assert(g965n_cp_security_request(0,1,2)==14);assert(cp_security_failed);
  assert(g965n_cp_security_request(2,0,0)==-EIO);assert(security_calls==1&&clock_on==1&&clock_off==1);}
 else if(!strcmp(test,"negative-error")){security_result=-EPERM;assert(g965n_cp_security_request(2,0,0)==-EPERM);assert(g965n_cp_security_request(0,1,2)==-EIO);assert(security_calls==1);}
 else if(!strcmp(test,"clock-faults")){clock_on_result=7;assert(g965n_cp_security_request(2,0,0)==-EIO);assert(!security_calls&&clock_on==1&&clock_off==1);
  clear();clock_on_result=-ENOSYS;assert(g965n_cp_security_request(2,0,0)==-ENOSYS);assert(!security_calls&&clock_off==1);
  clear();security_result=11;clock_off_result=9;assert(g965n_cp_security_request(2,0,0)==-EIO);assert(cp_security_failed&&security_calls==1);
  clear();security_result=-EPERM;clock_off_result=-ENOSYS;assert(g965n_cp_security_request(2,0,0)==-EPERM);}
 else if(!strcmp(test,"positive-pmu-error")){assert_result=9;assert(ss310ap_off(&mc)==-EIO);assert(cp_security_failed);}
 else if(!strcmp(test,"noop-reset-latch")){cp_security_failed=true;mc.phone_state=STATE_OFFLINE;assert(ss310ap_reset(&mc)==0);assert(cp_security_failed);assert(g965n_cp_security_request(2,0,0)==-EIO);}
 else if(!strcmp(test,"off-error")){assert_result=-ETIMEDOUT;assert(ss310ap_off(&mc)==-ETIMEDOUT);assert(cp_security_failed);assert(g965n_cp_security_request(2,0,0)==-EIO);assert(!security_calls);}
 else if(!strcmp(test,"reset-error")){assert_result=-EIO;assert(ss310ap_reset(&mc)==-EIO);assert(cp_security_failed&&!sw_resets);
  clear();mc.phone_state=STATE_ONLINE;release_result=-ETIMEDOUT;assert(ss310ap_reset(&mc)==-ETIMEDOUT);assert(cp_security_failed&&!sw_resets);}
 else if(!strcmp(test,"verified-reset")){cp_security_failed=true;g965n_cp_security_irq_failure();assert(ss310ap_off(&mc)==0);assert(!cp_security_failed);
  assert(g965n_cp_security_request(2,0,0)==0);}
 else if(!strcmp(test,"irq-during-reset-publish")){assert(g965n_cp_power_begin(true)==0);
  inject_target=&cp_security_irq_epoch;inject_after_epoch_read=true;assert(g965n_cp_power_end(0,true)==0);
  assert(g965n_cp_security_request(2,0,0)==-EIO);assert(!security_calls&&!clock_on);}
 else if(!strcmp(test,"irq-latch")){g965n_cp_security_irq_failure();assert(g965n_cp_security_request(2,0,0)==-EIO);assert(!security_calls);
  clear();statuses[0]=0;statuses[1]=1;status_count=2;irq_in_init=true;assert(g965n_cp_security_request(2,0,0)==-EIO);assert(!security_calls&&clock_on==clock_off);
  clear();irq_in_assert=true;assert(ss310ap_off(&mc)==-EIO);assert(cp_security_failed);
  clear();offline_in_assert=true;assert(ss310ap_off(&mc)==0);assert(!cp_security_failed);}
 else if(!strcmp(test,"on-dump-fault")){mailbox_result=-EINVAL;assert(ss310ap_on(&mc)==-EINVAL);assert(cp_security_failed&&!map_writes);
  clear();map_failure=1;assert(ss310ap_on(&mc)==-EACCES);assert(cp_security_failed);
  clear();manual_result=-EIO;assert(ss310ap_on(&mc)==-EIO);assert(cp_security_failed&&map_writes==1);
  clear();dump_result=-EFAULT;assert(ss310ap_dump_start(&mc)==-EFAULT);assert(cp_security_failed);}
 else if(!strcmp(test,"shutdown-completion-irqs")){offline_in_wait=true;assert(ss310ap_shutdown(&mc)==0);assert(!cp_security_failed);
  clear();mc.phone_state=STATE_ONLINE;fatal_in_wait=true;assert(ss310ap_shutdown(&mc)==-EIO);assert(cp_security_failed);}
 else if(!strcmp(test,"shutdown-error")){assert_result=-ETIMEDOUT;assert(ss310ap_shutdown(&mc)==-ETIMEDOUT);assert(cp_security_failed);}
 else if(!strcmp(test,"logging-guard")){statuses[0]=0;assert(security_request_cp_ram_logging()==-EAGAIN);assert(!security_calls&&!clock_on&&!init_calls&&!cp_security_failed);
  statuses[0]=0;statuses[1]=1;status_count=2;status_index=0;assert(g965n_cp_security_request(2,0,0)==0);assert(init_calls==1&&security_calls==1);
  clear();cp_security_failed=true;statuses[0]=0;assert(security_request_cp_ram_logging()==-EIO);assert(cp_security_failed&&!clock_on);
  clear();assert(security_request_cp_ram_logging()==0);assert(security_calls==1&&last_mode==5&&clock_on==clock_off);}
 else if(!strcmp(test,"ctrl-write-errors")){control_result=-1;assert(ctrl_write(CP_CTRL_NS,U32_MAX,123)==-EIO);assert(ctrl_writes==1);
  clear();control_result=1;assert(ctrl_write(CP_CTRL_NS,U32_MAX,123)==-EIO);
  clear();assert(ctrl_write(CP_CTRL_NS,U32_MAX,123)==0);}
 else if(!strcmp(test,"serialized-transition")){pthread_t a,b;void *ra,*rb;atomic_store(&hold_assert,1);assert(!pthread_create(&a,NULL,off_thread,&mc));
  for(int i=0;i<10000&&!atomic_load(&assert_entered);i++)usleep(100);assert(atomic_load(&assert_entered));
  assert(!pthread_create(&b,NULL,security_thread,NULL));usleep(20000);assert(!security_calls&&!clock_on);
  atomic_store(&release_assert,1);assert(!pthread_join(a,&ra));assert(!pthread_join(b,&rb));assert(!ra&&!rb&&security_calls==1);}
 else assert(!"unknown scenario");balanced();return 0;}
'''


class CPSecurityGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        compiler=shutil.which('cc')
        if not compiler:raise unittest.SkipTest('Host C compiler unavailable')
        bodies=[]
        link='experiments/modem/link_device_shmem.c'
        for name in ('g965n_cp_security_irq_failure','g965n_cp_security_offline_irq','g965n_cp_power_begin','g965n_cp_power_expect_offline','g965n_cp_power_end','g965n_cp_security_request','shmem_security_request'):
            bodies.append(function(link,name))
        ctrl='experiments/modem/modem_ctrl_ss310ap.c'
        for name in ('ss310ap_on','ss310ap_off','ss310ap_shutdown','ss310ap_reset','ss310ap_dump_start'):
            bodies.append(function(ctrl,name))
        bodies.append(function('experiments/modem/modem_utils.c','security_request_cp_ram_logging'))
        for name in ('ctrl_read','ctrl_write'):bodies.append(function('experiments/modem/zrn_cp_pmu.c',name))
        code=SHIM+'\n'+'\n\n'.join(bodies)+'\n'+HARNESS
        src=Path(cls.temp.name)/'production-guard.c';src.write_text(code)
        cls.binary=Path(cls.temp.name)/'production-guard'
        result=subprocess.run([compiler,'-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function',
                        '-Wno-unused-variable','-Wno-misleading-indentation','-pthread',str(src),'-o',str(cls.binary)],check=False,capture_output=True,text=True,timeout=30)
        if result.returncode:raise AssertionError(result.stderr)

    def test_fault_injection_on_production_functions(self):
        for scenario in ('pmu-init-fail','status-fail','post-init-unready','cold-success','mode2-positive-abi',
            'terminal-error','negative-error','clock-faults','positive-pmu-error','noop-reset-latch','off-error','reset-error','verified-reset','irq-during-reset-publish','irq-latch',
            'on-dump-fault','shutdown-completion-irqs','shutdown-error','logging-guard','ctrl-write-errors','serialized-transition'):
            with self.subTest(scenario=scenario):
                subprocess.run([str(self.binary),scenario],check=True,capture_output=True,text=True,timeout=5)


if __name__=='__main__':unittest.main()

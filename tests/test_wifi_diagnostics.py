#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Host tests using actual patched C functions. Set WIFI_KERNEL_SOURCE to Linux tree."""
import hashlib
import types
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'scripts/build/g965n-wifi-diagnostics.py'
D = types.ModuleType('wifi_diag')
exec(compile(HELPER.read_text(), str(HELPER), 'exec'), D.__dict__)
SOURCE = Path(os.environ.get('WIFI_KERNEL_SOURCE', str(ROOT / '.local/context/wifi-diagnostics-pristine')))


def extract(text, name):
    match = re.search(r'(?m)^static [^;{}]*?\b' + re.escape(name) + r'\([^;{}]*\)\s*\{', text)
    if not match:
        raise ValueError('C function definition missing: ' + name)
    start = match.start()
    brace = match.end() - 1
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


STUBS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <stddef.h>
typedef unsigned int uint;
typedef uint32_t u32;
typedef int32_t s32;
typedef uint8_t u8;
#define BRCMF_C_SET_ROAM_TRIGGER 55
#define BRCMF_C_SET_VAR 263
#define BRCMF_BUS_UP 1
#define BRCMF_DCMD_MAXLEN 8192
#define BRCMF_MAX_IFS 16
#define BRCMF_E_IF_FLAG_NOIF 1
#define BRCMF_E_IF_ROLE_P2P_CLIENT 4
#define BRCMF_E_IF_ROLE_STA 0
#define ETH_ALEN 6
#define EIO 5
#define EBADE 52
#define min_t(type,a,b) ((type)(a)<(type)(b)?(type)(a):(type)(b))
#define brcmf_dbg(...) ((void)0)
#define brcmf_dbg_hex_dump(...) ((void)0)
#define be16_to_cpu(x) __builtin_bswap16(x)
#define be32_to_cpu(x) __builtin_bswap32(x)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
enum brcmf_fweh_event_code { BRCMF_E_IF=54, BRCMF_E_TDLS_PEER_EVENT=92 };
struct work_struct { int dummy; };
struct brcmf_bus { int state; };
struct brcmf_pub;
struct brcmf_if { struct brcmf_pub *drvr; int ifidx; bool fwil_fwerr; };
struct brcmf_event_msg_be { uint16_t version,flags;u32 event_code,status,reason,auth_type,datalen;u8 addr[6];char ifname[16];u8 ifidx,bsscfgidx; };
struct brcmf_event_msg { uint16_t version,flags;u32 event_code,status,reason,auth_type,datalen;u8 addr[6];char ifname[16];u8 ifidx,bsscfgidx; };
struct brcmf_if_event { u8 ifidx,action,flags,bsscfgidx,role; };
struct brcmf_fweh_queue_item {u32 code;struct brcmf_event_msg_be emsg;u32 datalen;u8 data[];};
struct brcmf_fweh_info {struct work_struct event_work;struct brcmf_pub *drvr;bool p2pdev_setup_ongoing;};
struct brcmf_pub {void *wiphy;struct brcmf_bus *bus_if;struct brcmf_fweh_info *fweh;struct brcmf_if *iflist[BRCMF_MAX_IFS];};
static int log_count,proto_count,handler_count,free_count,transport_ret,firmware_ret;
static bool log_enabled=true;
static char log_text[1024];
static struct brcmf_fweh_queue_item *queued;
static void test_log(const char *fmt,...) { va_list args;va_start(args,fmt);vsnprintf(log_text,sizeof(log_text),fmt,args);va_end(args);log_count++; }
#define net_ratelimit() (log_enabled)
#define wiphy_err(wiphy,fmt,...) test_log(fmt,##__VA_ARGS__)
#define bphy_err(drvr,fmt,...) test_log(fmt,##__VA_ARGS__)
static int brcmf_proto_set_dcmd(struct brcmf_pub *d,int i,u32 c,void *v,u32 n,s32 *e) {proto_count++;*e=firmware_ret;return transport_ret;}
#define brcmf_proto_query_dcmd brcmf_proto_set_dcmd
static struct brcmf_fweh_queue_item *brcmf_fweh_dequeue_event(struct brcmf_fweh_info *f) {struct brcmf_fweh_queue_item *e=queued;queued=NULL;return e;}
static void brcmf_fweh_map_fwevt_code(struct brcmf_fweh_info *f,u32 raw,enum brcmf_fweh_event_code *c) {*c=raw;}
static void brcmf_fweh_handle_if_event(struct brcmf_pub *d,struct brcmf_event_msg *m,void *v) {volatile u8 last=((u8 *)v)[4];(void)last;handler_count++;}
static int brcmf_fweh_call_event_handler(struct brcmf_pub *d,struct brcmf_if *i,u32 c,struct brcmf_event_msg *m,void *v) {handler_count++;return 0;}
static void kfree(void *p) {free_count++;free(p);}
'''
CASES = r'''
int main(void) {
 struct brcmf_bus bus={.state=BRCMF_BUS_UP};
 struct brcmf_fweh_info f={.p2pdev_setup_ongoing=true};
 struct brcmf_pub d={.bus_if=&bus,.fweh=&f};
 struct brcmf_if i={.drvr=&d,.ifidx=0};
 f.drvr=&d;d.iflist[0]=&i;
 /* Exact NUL-terminated allowlist; no overread of short or null buffers. */
 for(unsigned n=0;n<9;n++) {
  char *p=malloc(n?n:1);memset(p,'x',n);
  assert(!brcmf_g965n_diag_cmd(263,p,n,true));free(p);
 }
 assert(!brcmf_g965n_diag_cmd(263,NULL,9,true));
 assert(brcmf_g965n_diag_cmd(263,"p2p_disc",9,true));
 assert(brcmf_g965n_diag_cmd(263,"p2p_disc\0trailer",17,true));
 assert(!brcmf_g965n_diag_cmd(263,"p2p_discX",9,true));
 assert(!brcmf_g965n_diag_cmd(263,"privateSSID",12,true));
 assert(!brcmf_g965n_diag_cmd(263,"p2p_disc",9,false));
 assert(brcmf_g965n_diag_cmd(55,NULL,0,true));
 assert(!brcmf_g965n_diag_cmd(54,NULL,0,true));
 /* Production command function: same calls and errno/raw-fwerr returns. */
 transport_ret=0;firmware_ret=-23;log_count=proto_count=0;
 assert(brcmf_fil_cmd_data(&i,55,NULL,0,true)==-EBADE);
 assert(proto_count==1&&log_count==1);
 assert(!strcmp(log_text,"g965n_fw cmd=55 ifidx=0 fwerr=-23\n"));
 log_count=0;assert(brcmf_fil_cmd_data(&i,263,"privateSSID",12,true)==-EBADE);assert(log_count==0);
 i.fwil_fwerr=true;assert(brcmf_fil_cmd_data(&i,55,NULL,0,true)==-23);i.fwil_fwerr=false;
 transport_ret=-7;log_count=0;assert(brcmf_fil_cmd_data(&i,55,NULL,0,true)==-7);assert(log_count==0);
 transport_ret=0;firmware_ret=0;log_count=0;assert(brcmf_fil_cmd_data(&i,55,NULL,0,true)==0);assert(log_count==0);
 log_enabled=false;firmware_ret=-23;log_count=0;
 assert(brcmf_fil_cmd_data(&i,55,NULL,0,true)==-EBADE);assert(log_count==0);
 log_enabled=true;
 /* Actual worker: lengths0..4 free exactly once with NO IF reader. */
 for(unsigned n=0;n<=5;n++) {
  queued=calloc(1,sizeof(*queued)+n);queued->code=BRCMF_E_IF;queued->datalen=n;
  queued->emsg.version=__builtin_bswap16(2);queued->emsg.datalen=__builtin_bswap32(n);
  if(n==5)queued->data[1]=1;
  handler_count=free_count=log_count=0;
  brcmf_fweh_event_worker(&f.event_work);
  assert(free_count==1&&handler_count==(n==5));
  assert(log_count==1);assert(strstr(log_text,n<5?"disposition=1":"disposition=0"));
 }
 /* Diagnostic allowlist and reason classification only; never payload strings. */
 struct brcmf_fweh_queue_item *e=calloc(1,sizeof(*e)+32);
 e->code=BRCMF_E_IF;e->datalen=5;
 e->emsg.version=__builtin_bswap16(2);e->emsg.status=__builtin_bswap32(3);e->emsg.reason=__builtin_bswap32(4);
 strcpy(e->emsg.ifname,"privateSSID");memcpy(e->data+5,"privateSSID",12);
 for(unsigned reason=0;reason<=5;reason++) {
  memset(e->data,0,5);e->datalen=5;e->emsg.bsscfgidx=0;
  if(reason==1)e->datalen=4;
  if(reason==2)e->emsg.bsscfgidx=BRCMF_MAX_IFS;
  if(reason==3){e->data[2]=1;e->data[4]=1;}
  if(reason==4)e->data[0]=BRCMF_MAX_IFS;
  if(reason==5)e->data[3]=BRCMF_MAX_IFS;
  log_count=0;brcmf_g965n_diag_if(&d,e);assert(log_count==1);
  char expected[24];snprintf(expected,sizeof(expected),"disposition=%u",reason);
  assert(strstr(log_text,expected));assert(!strstr(log_text,"privateSSID"));
 }
 /* Rate denial cannot suppress cleanup or change command returns. */
 e->datalen=5;e->data[0]=0;e->data[3]=0;e->emsg.bsscfgidx=0;
 log_enabled=false;log_count=0;brcmf_g965n_diag_if(&d,e);assert(log_count==0);
 queued=calloc(1,sizeof(*queued)+4);queued->code=BRCMF_E_IF;queued->datalen=4;
 handler_count=free_count=0;brcmf_fweh_event_worker(&f.event_work);
 assert(log_count==0&&free_count==1&&handler_count==0);
 queued=calloc(1,sizeof(*queued)+5);queued->code=BRCMF_E_IF;queued->datalen=5;
 handler_count=free_count=0;brcmf_fweh_event_worker(&f.event_work);
 assert(log_count==0&&free_count==1&&handler_count==1);
 log_enabled=true;
 e->code=1;log_count=0;brcmf_g965n_diag_if(&d,e);assert(log_count==0);
 e->code=BRCMF_E_IF;f.p2pdev_setup_ongoing=false;brcmf_g965n_diag_if(&d,e);assert(log_count==0);
 free(e);
 puts("Wi-Fi production C filter/errno/worker bounds/redaction cases PASS");
 return 0;
}
'''


ROAM_STUBS = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdatomic.h>
typedef uint32_t u32; typedef int32_t s32; typedef uint32_t __le32;
typedef _Atomic int atomic_t;
#define ATOMIC_INIT(x) ATOMIC_VAR_INIT(x)
static int atomic_cmpxchg(atomic_t *p,int old,int value) {atomic_compare_exchange_strong(p,&old,value);return old;}
#define BRCM_CC_4361_CHIP_ID 0x4361
#define BRCMF_C_SET_ROAM_TRIGGER 55
#define BRCMF_C_SET_ROAM_DELTA 57
#define BRCMF_DEFAULT_BCN_TIMEOUT_ROAM_OFF 10
#define BRCMF_DEFAULT_BCN_TIMEOUT_ROAM_ON 2
#define WL_ROAM_TRIGGER_LEVEL (-75)
#define WL_ROAM_DELTA 20
#define BRCM_BAND_ALL 3
#define cpu_to_le32(x) ((u32)(x))
#define brcmf_dbg(...) ((void)0)
struct brcmf_bus {u32 chip;};
struct settings {bool roamoff;};
struct brcmf_pub {void *wiphy;struct brcmf_bus *bus_if;struct settings *settings;};
struct brcmf_if {struct brcmf_pub *drvr;int ifidx;bool fwil_fwerr;};
static bool board=true;
static int calls,query_count,logs,fail_at,ret_value=-7,query_ret[2];
static u32 query_value[2]={1,5};
static char order[16][40],messages[4][160];
static u32 payload[16][2];
static bool of_machine_is_compatible(const char *s) {assert(!strcmp(s,"samsung,star2lte"));return board;}
static void log_numeric(const char *fmt,...) {va_list a;va_start(a,fmt);assert(logs<4);vsnprintf(messages[logs++],160,fmt,a);va_end(a);}
#define wiphy_info(wiphy,fmt,...) log_numeric(fmt,##__VA_ARGS__)
#define bphy_err(...) ((void)0)
static int brcmf_fil_iovar_int_get(struct brcmf_if *ifp,const char *name,u32 *value) {
 int kind=!strcmp(name,"preinit_status")?0:1;
 assert(kind==0||!strcmp(name,"wnm_bsstrans_resp"));
 snprintf(order[calls++],40,"G%d",kind);query_count++;
 *value=query_value[kind];return query_ret[kind];
}
static int brcmf_fil_iovar_int_set(struct brcmf_if *ifp,const char *name,u32 value) {
 int kind=!strcmp(name,"bcn_timeout")?1:2;assert(kind==1||!strcmp(name,"roam_off"));
 snprintf(order[calls],40,"S%d",kind);payload[calls++][0]=value;
 return fail_at==kind?ret_value:0;
}
static int brcmf_fil_cmd_data_set(struct brcmf_if *ifp,u32 cmd,void *data,u32 len) {
 assert(len==8);assert(cmd==55||cmd==57);
 snprintf(order[calls],40,"C%u",cmd);memcpy(payload[calls++],data,8);
 return fail_at==(int)cmd?ret_value:0;
}
static void reset(void) {calls=query_count=logs=fail_at=0;query_ret[0]=query_ret[1]=0;memset(order,0,sizeof(order));memset(payload,0,sizeof(payload));}
"""
ROAM_CASES = r"""
int main(void) {
 struct brcmf_bus bus={.chip=BRCM_CC_4361_CHIP_ID};struct settings setting={.roamoff=false};
 struct brcmf_pub d={.bus_if=&bus,.settings=&setting};struct brcmf_if ifp={.drvr=&d,.fwil_fwerr=true};
 /* Wrong board/chip/interface cannot query OR consume the one-shot marker. */
 board=false;brcmf_g965n_roam_policy_diag(&ifp);assert(calls==0);
 board=true;bus.chip=0x1234;brcmf_g965n_roam_policy_diag(&ifp);assert(calls==0);
 bus.chip=BRCM_CC_4361_CHIP_ID;ifp.ifidx=1;brcmf_g965n_roam_policy_diag(&ifp);assert(calls==0);
 ifp.ifidx=0;brcmf_g965n_roam_policy_diag(&ifp);assert(query_count==2&&calls==2&&logs==2);
 assert(strstr(messages[0],"kind=0 ret=0 valid=1 value=1"));
 assert(strstr(messages[1],"kind=1 ret=0 valid=1 value=5"));
 brcmf_g965n_roam_policy_diag(&ifp);assert(query_count==2&&calls==2&&logs==2);
 assert(ifp.fwil_fwerr); /* never toggle a shared firmware error-mode flag */
 /* Actual original and patched roaming functions: same ordered writes,
    same bytes and same returns, including every existing failure path. */
 int failures[]={0,1,2,55,57};
 for(unsigned k=0;k<sizeof(failures)/sizeof(failures[0]);k++) {
  reset();fail_at=failures[k];int old=brcmf_dongle_roam_original(&ifp);
  int old_count=calls;char saved_order[16][40];u32 saved_payload[16][2];
  memcpy(saved_order,order,sizeof(order));memcpy(saved_payload,payload,sizeof(payload));
  reset();atomic_store(&brcmf_g965n_roam_diag_done,0);fail_at=failures[k];
  query_ret[0]=-52;query_ret[1]=-7;query_value[0]=0xdeadbeef;query_value[1]=0xffffffff;
  int current=brcmf_dongle_roam(&ifp);
  assert(current==old&&query_count==2&&calls==old_count+2);
  assert(!strcmp(order[0],"G0")&&!strcmp(order[1],"G1"));
  for(int n=0;n<old_count;n++) {assert(!strcmp(order[n+2],saved_order[n]));assert(!memcmp(payload[n+2],saved_payload[n],8));}
  assert(strstr(messages[0],"kind=0 ret=-52 valid=0 value=0"));
  assert(strstr(messages[1],"kind=1 ret=-7 valid=0 value=0"));
 }
 reset();atomic_store(&brcmf_g965n_roam_diag_done,0);query_value[0]=1;query_value[1]=5;
 assert(brcmf_dongle_roam(&ifp)==0);assert(calls==6&&query_count==2);
 assert(!strcmp(order[4],"C55")); /* observed policy5 does NOT alter behavior */
 puts("Wi-Fi actual C boot-policy guards/once/two-GET/order/invalid values PASS");return 0;
}
"""



class WifiDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {}
        for name in D.ORIGINAL:
            p = SOURCE / name
            if not p.exists():
                p = SOURCE / D.REL / name
            if not p.exists():
                raise unittest.SkipTest('set WIFI_KERNEL_SOURCE to exact reviewed source tree')
            cls.original[name] = p.read_bytes()
            if hashlib.sha256(cls.original[name]).hexdigest() != D.ORIGINAL[name]:
                raise AssertionError('fixture must be the exact pristine source')

    def test_apply_idempotence_and_drift_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/D.REL).mkdir(parents=True)
            for name,data in self.original.items():
                (root/D.REL/name).write_bytes(data)
            self.assertEqual(D.apply(root),3)
            self.assertEqual(D.apply(root),0)
            for name in self.original:
                patched=(root/D.REL/name).read_bytes()
                self.assertTrue(patched.startswith(b'// SPDX-License-Identifier: ISC\n'))
                self.assertIn(b'Broadcom Corporation',patched)
                self.assertEqual(hashlib.sha256(patched).hexdigest(),D.PATCHED[name])
            (root/D.REL/'fwil.c').write_bytes(self.original['fwil.c'])
            (root/D.REL/'cfg80211.c').write_bytes(self.original['cfg80211.c'])
            (root/D.REL/'fweh.c').write_bytes(b'unreviewed drift')
            with self.assertRaises(ValueError):D.apply(root)
            self.assertEqual((root/D.REL/'fwil.c').read_bytes(),self.original['fwil.c'])
            self.assertEqual((root/D.REL/'cfg80211.c').read_bytes(),self.original['cfg80211.c'])

    def test_existing_two_file_cache_adds_only_policy_observer(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/D.REL).mkdir(parents=True)
            for name,data in self.original.items():
                (root/D.REL/name).write_bytes(data if name=='cfg80211.c' else D.transform(name,data))
            before={name:(root/D.REL/name).read_bytes() for name in ('fwil.c','fweh.c')}
            self.assertEqual(D.apply(root),1)
            self.assertEqual(D.apply(root),0)
            for name,data in before.items():self.assertEqual((root/D.REL/name).read_bytes(),data)

    def test_actual_c_with_address_and_undefined_sanitizers(self):
        fwil=D.transform('fwil.c',self.original['fwil.c']).decode()
        fweh=D.transform('fweh.c',self.original['fweh.c']).decode()
        functions='\n'.join([D.FWIL_HELPER,extract(fwil,'brcmf_fil_cmd_data'),D.EVENT_HELPER,extract(fweh,'brcmf_fweh_event_worker')])
        with tempfile.TemporaryDirectory() as td:
            c=Path(td)/'test.c';binary=Path(td)/'test';c.write_text(STUBS+functions+CASES)
            subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-fsanitize=address,undefined',str(c),'-o',str(binary)],check=True)
            r=subprocess.run([str(binary)],capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'},check=True)
            self.assertIn('PASS',r.stdout)


    def test_actual_roam_c_guards_order_failure_values_and_unchanged_writes(self):
        original=self.original['cfg80211.c'].decode()
        patched=D.transform('cfg80211.c',self.original['cfg80211.c']).decode()
        function=extract(patched,'brcmf_dongle_roam')
        baseline=extract(original,'brcmf_dongle_roam').replace('brcmf_dongle_roam(', 'brcmf_dongle_roam_original(',1)
        # The only alteration to the existing function is the leading observer.
        self.assertEqual(function.replace('\tbrcmf_g965n_roam_policy_diag(ifp);\n\n',''),extract(original,'brcmf_dongle_roam'))
        with tempfile.TemporaryDirectory() as td:
            c=Path(td)/'roam.c';binary=Path(td)/'roam'
            c.write_text(ROAM_STUBS+D.ROAM_HELPER+baseline+'\n'+function+ROAM_CASES)
            subprocess.run([os.environ.get('CC','cc'),'-std=c11','-g','-fsanitize=address,undefined',str(c),'-o',str(binary)],check=True)
            r=subprocess.run([str(binary)],capture_output=True,text=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'},check=True)
            self.assertIn('PASS',r.stdout)



if __name__ == '__main__':unittest.main()

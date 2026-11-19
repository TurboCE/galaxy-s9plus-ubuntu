# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib
import importlib.util
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts/build'/('g965n-p2p-'+name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
c=module('control');s=module('setup')

STUB=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>
typedef uint8_t u8;typedef uint32_t u32;
#define BRCMF_MAX_IFS 16
#define ETH_ALEN 6
#define BRCMF_VIF_STATUS_CONNECTED 1
#define BRCMF_VIF_STATUS_CONNECTING 2
#define test_bit(n,p) (!!(*(p)&(1UL<<(n))))
#define BRCMF_PROTO_MSGBUF 1
#define BRCM_CC_4361_CHIP_ID 4361
#define module_param_named(...)
#define MODULE_PARM_DESC(...)
#define wiphy_info(...) ((void)0)
#define wiphy_warn(...) ((void)0)
#define ERR_PTR(v) ((void *)(intptr_t)(v))
#define PTR_ERR(v) ((int)(intptr_t)(v))
#define IS_ERR(v) ((uintptr_t)(v)>=(uintptr_t)-4095)
struct bus {int chip,proto_type;};
struct settings {bool p2p_enable;};
struct proto {void (*del_if)(void *);};
struct brcmf_if;
struct brcmf_pub {struct bus *bus_if;struct settings *settings;struct proto *proto;struct brcmf_if *iflist[16];int if2bss[16];void *wiphy;};
struct brcmf_cfg80211_vif {struct brcmf_if *ifp;unsigned long sme_state;};
struct brcmf_if {struct brcmf_pub *drvr;int ifidx,bsscfgidx;void *ndev;struct brcmf_cfg80211_vif *vif;};
static bool target=true;
static bool of_machine_is_compatible(const char *s) {assert(!strcmp(s,"samsung,star2lte"));return target;}
static int sets,gets,adds,on_error,get_error,off_error,alloc_error;
static u32 actual_bss=2,apsta=1;
static int apsta_error,overrides,setups,setup_error;
static struct brcmf_if allocated;
static int brcmf_fil_iovar_int_set(struct brcmf_if *i,const char *n,int v) {(void)i;assert(!strcmp(n,"p2p_disc"));sets++;return v?on_error:off_error;}
static int brcmf_fil_iovar_int_get(struct brcmf_if *i,const char *n,u32 *v) {(void)i;if(!strcmp(n,"apsta")){*v=apsta;return apsta_error;}assert(!strcmp(n,"p2p_dev"));gets++;*v=actual_bss;return get_error;}
static int brcmf_p2p_set_firmware(struct brcmf_if *i,u8 *a) {(void)i;(void)a;setups++;return setup_error;}
static int brcmf_fil_iovar_data_set(struct brcmf_if *i,const char *n,u8 *a,int size) {(void)i;(void)a;assert(!strcmp(n,"p2p_da_override")&&size==6);overrides++;return 0;}
static struct brcmf_if *brcmf_add_if(struct brcmf_pub *d,int bss,int idx,bool p2p,const char *n,u8 *mac) {
 (void)n;(void)mac;adds++;assert(bss>0&&bss<16&&idx==0&&p2p&&!d->settings->p2p_enable&&!d->iflist[bss]&&d->if2bss[0]==0);
 if(alloc_error)return ERR_PTR(alloc_error);
 allocated=(struct brcmf_if){.drvr=d,.ifidx=0,.bsscfgidx=bss};d->iflist[bss]=&allocated;return &allocated;
}
'''
CASES=r'''
static void forbidden_del(void *x) {(void)x;assert(0);}
int main(void) {
 struct bus bus={4361,1};struct settings settings={0};struct proto proto={0};
 struct brcmf_pub d={.bus_if=&bus,.settings=&settings,.proto=&proto};
 struct brcmf_if pri={.drvr=&d,.ndev=(void *)1};struct brcmf_cfg80211_vif vif={0};u8 mac[6]={0};d.iflist[0]=&pri;
 struct brcmf_cfg80211_vif primary_vif={.ifp=&pri};pri.vif=&primary_vif;
 primary_vif.sme_state=1UL<<BRCMF_VIF_STATUS_CONNECTED;
 assert(brcmf_g965n_prepare_control(&pri,mac)==0&&setups==0&&overrides==1);
 apsta=0;assert(brcmf_g965n_prepare_control(&pri,mac)==-EBUSY&&setups==0);
 primary_vif.sme_state=1UL<<BRCMF_VIF_STATUS_CONNECTING;assert(brcmf_g965n_prepare_control(&pri,mac)==-EBUSY&&setups==0);
 primary_vif.sme_state=0;setup_error=-ETIMEDOUT;assert(brcmf_g965n_prepare_control(&pri,mac)==-ETIMEDOUT&&setups==1);
 apsta=1;apsta_error=-EIO;assert(brcmf_g965n_prepare_control(&pri,mac)==-EIO&&setups==1);apsta_error=0;sets=gets=adds=0;
 assert(!g965n_legacy_p2pdev);assert(!brcmf_g965n_control_scope(0));
 on_error=-EIO;assert(brcmf_g965n_create_control(&pri,&vif,mac)==-EIO&&sets==1&&gets==0&&adds==0);on_error=0;sets=0;
 get_error=-ENODEV;off_error=-EBUSY;assert(brcmf_g965n_create_control(&pri,&vif,mac)==-ENODEV&&sets==2&&adds==0);get_error=off_error=0;
 for(unsigned int k=0;k<3;k++) {actual_bss=k==0?0:k==1?16:UINT32_MAX;assert(brcmf_g965n_create_control(&pri,&vif,mac)==-ERANGE&&adds==0);}
 actual_bss=2;d.iflist[2]=&pri;assert(brcmf_g965n_create_control(&pri,&vif,mac)==-EEXIST&&d.iflist[2]==&pri&&adds==0);d.iflist[2]=0;
 alloc_error=-ENOMEM;assert(brcmf_g965n_create_control(&pri,&vif,mac)==-ENOMEM&&!vif.ifp&&!d.iflist[2]);alloc_error=0;
 for(int gate=0;gate<5;gate++) {
  int old=sets;bus.proto_type=gate==0?0:1;settings.p2p_enable=gate==1;proto.del_if=gate==2?forbidden_del:0;d.if2bss[0]=gate==3?2:0;target=gate!=4;
  assert(brcmf_g965n_create_control(&pri,&vif,mac)==-EOPNOTSUPP&&sets==old);
 }
 target=true;d.if2bss[0]=0;settings.p2p_enable=false;proto.del_if=0;bus.proto_type=1;
 assert(brcmf_g965n_create_control(&pri,&vif,mac)==0&&vif.ifp==&allocated&&allocated.vif==&vif);
 assert(d.iflist[0]==&pri&&d.if2bss[0]==0&&d.iflist[2]==&allocated&&brcmf_g965n_is_control(&vif));
 g965n_legacy_p2pdev=false;assert(brcmf_g965n_is_control(&vif)); /* Cleanup does not depend on mutable opt-in. */
 allocated.ndev=(void *)1;assert(!brcmf_g965n_is_control(&vif));
 return 0;
}
'''

class P2pControlTests(unittest.TestCase):
    def test_actual_c_real_context_gates_and_failure_cleanup(self):
        cc=shutil.which('cc')
        if not cc:self.skipTest('C compiler unavailable')
        checked=s.HELPERS[:s.HELPERS.index('static void')]
        with tempfile.TemporaryDirectory() as temporary:
            p=Path(temporary);(p/'test.c').write_text(STUB+checked+c.HELPER+CASES)
            subprocess.run([cc,'-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)

    def test_atomic_pins_idempotence_and_upstream_notices(self):
        cache=ROOT/'.local/context/wifi-diagnostics-pristine'
        if not all((cache/n).is_file() for n in ['p2p.c','core.c']):self.skipTest('Pinned primary sources unavailable')
        p2p=s.transform((cache/'p2p.c').read_bytes());core=(cache/'core.c').read_bytes()
        self.assertEqual(hashlib.sha256(p2p).hexdigest(),c.P2P_OLD)
        self.assertEqual(hashlib.sha256(core).hexdigest(),c.CORE_OLD)
        previous=cache/'p2p-control-v1.c'
        if previous.exists():
            self.assertEqual(hashlib.sha256(previous.read_bytes()).hexdigest(),c.P2P_PREVIOUS)
            self.assertEqual(c.upgrade(previous.read_bytes()),c.p2p_transform(p2p))
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)/c.BASE;base.mkdir(parents=True);a=base/'p2p.c';b=base/'core.c'
            a.write_bytes(p2p);b.write_bytes(b'unreviewed')
            with self.assertRaises(ValueError):c.apply(temporary)
            self.assertEqual(a.read_bytes(),p2p)
            b.write_bytes(core);c.apply(temporary);s.apply(temporary);c.apply(temporary)
            self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(),c.P2P_NEW)
            self.assertEqual(hashlib.sha256(b.read_bytes()).hexdigest(),c.CORE_NEW)
            self.assertTrue(a.read_bytes().startswith(p2p[:p2p.index(b'#include')]))
            self.assertIn(b'if (ifp && !ifp->ndev)',b.read_bytes())

if __name__=='__main__':unittest.main()

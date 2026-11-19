# SPDX-License-Identifier: GPL-2.0-only
"""Compile the actual injected C channel-state predicate; no device operations."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wifi',ROOT/'scripts/build/g965n-wifi-diagnostics.py')
wifi=importlib.util.module_from_spec(spec);spec.loader.exec_module(wifi)

STUB=r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
#define BRCMF_VIF_STATUS_CONNECTED 0
#define BRCMF_VIF_STATUS_AP_CREATED 1
#define BRCM_CC_4361_CHIP_ID 4361
#define BRCMF_PROTO_MSGBUF 1
#define NL80211_IFTYPE_P2P_CLIENT 8
#define NL80211_IFTYPE_P2P_GO 9
#define test_bit(n,p) (!!(*(p)&(1UL<<(n))))
struct bus {int chip,proto_type;};
struct brcmf_pub {struct bus *bus_if;};
struct vif {unsigned long sme_state;};
struct brcmf_if {struct brcmf_pub *drvr;struct vif *vif;};
struct wireless_dev {int iftype;};
static bool target=true;
static bool of_machine_is_compatible(const char *s) {assert(!strcmp(s,"samsung,star2lte"));return target;}
'''
CASES=r'''
int main(void) {
 struct bus bus={4361,1};struct brcmf_pub d={&bus};struct vif vif={0};
 struct brcmf_if i={&d,&vif};struct wireless_dev w={8};
 assert(brcmf_g965n_p2p_has_no_channel(&i,&w));
 vif.sme_state=1;assert(!brcmf_g965n_p2p_has_no_channel(&i,&w));
 vif.sme_state=2;assert(brcmf_g965n_p2p_has_no_channel(&i,&w));
 w.iftype=9;assert(!brcmf_g965n_p2p_has_no_channel(&i,&w));
 vif.sme_state=0;assert(brcmf_g965n_p2p_has_no_channel(&i,&w));
 for(int role=0;role<12;role++) {
  w.iftype=role;if(role!=8&&role!=9)assert(!brcmf_g965n_p2p_has_no_channel(&i,&w));
 }
 w.iftype=8;target=false;assert(!brcmf_g965n_p2p_has_no_channel(&i,&w));target=true;
 bus.chip=4359;assert(!brcmf_g965n_p2p_has_no_channel(&i,&w));bus.chip=4361;
 bus.proto_type=0;assert(!brcmf_g965n_p2p_has_no_channel(&i,&w));bus.proto_type=1;
 i.vif=0;assert(!brcmf_g965n_p2p_has_no_channel(&i,&w));
 assert(!brcmf_g965n_p2p_has_no_channel(0,&w));
}
'''


class ChannelState(unittest.TestCase):
    def test_actual_c_scope_and_active_vs_idle_state(self):
        compiler=shutil.which('cc')
        if not compiler:self.skipTest('C compiler required')
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'test.c';out=Path(name)/'test'
            path.write_text(STUB+wifi.CHANNEL_HELPER+CASES)
            subprocess.run([compiler,'-Wall','-Wextra','-Werror',str(path),'-o',str(out)],check=True)
            subprocess.run([str(out)],check=True)


if __name__=='__main__':unittest.main()

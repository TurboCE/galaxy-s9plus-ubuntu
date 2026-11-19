# SPDX-License-Identifier: GPL-2.0-only
"""Compile the actual board power functions against injected ACPM failures."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'experiments/sensors/zrn_bbd_board.c'


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
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/types.h>
typedef uint8_t u8;
struct device {int unused;};struct device_attribute {int unused;};
#define S2MPS18_L37CTRL 0x6e
#define LDO_ON_MODE 0xc0
#define ZRN_GPIO_GPS_PWR 3
static void *zrn_gpios[4];
static bool supply_cut;
static int updates,reads,sleeps,parks,restores,enabled,disabled,logs;
static int update_results[3],read_result,restore_result;
static int later_read_result;
static bool parked_cs_inactive;
static unsigned int update_values[3];
static u8 read_value;
#define pr_err(...) ((void)logs++)
#define pr_info(...) ((void)0)
#define sysfs_emit(b,fmt,...) snprintf(b,32,fmt,##__VA_ARGS__)
static int s9p_acpm_pmic_update(u8 reg,u8 value,u8 mask) {
 assert(reg==0x6e&&mask==0xc0&&updates<3);update_values[updates]=value;return update_results[updates++];
}
static int s9p_acpm_pmic_read(u8 reg,u8 *value) {
 assert(reg==0x6e);reads++;*value=read_value;return reads>1&&later_read_result?later_read_result:read_result;
}
static void msleep(unsigned int ms) {assert(ms==20||ms==100||ms==1000);sleeps++;}
static void hub_pins_park(bool inactive) {parks++;parked_cs_inactive=inactive;}
static int hub_pins_restore(void) {restores++;return restore_result;}
static void gpiod_set_value(void *gpio,int value) {(void)gpio;if(value)enabled++;else disabled++;}
static int kstrtoll(const char *s,unsigned int base,long long *value) {
 char *end;*value=strtoll(s,&end,base);return end==s||*end?-EINVAL:0;
}
static void reset(void) {
 updates=reads=sleeps=parks=restores=enabled=disabled=logs=0;
 for(int i=0;i<3;i++)update_results[i]=update_values[i]=0;
 read_result=restore_result=later_read_result=0;read_value=0xce;supply_cut=false;parked_cs_inactive=false;
}
'''
CASES=r'''
int main(void) {
 char buffer[32];
 reset();assert(hub_supply_enable()==0&&updates==1&&reads==1&&sleeps==1&&update_values[0]==0xc0);
 for(int r=-110;r<=255;r+=r<0?110:r==0?1:254) {
  reset();update_results[0]=r;
  int expected=r>0?-EIO:r;
  assert(hub_supply_enable()==expected);
  if(r)assert(reads==0&&sleeps==0);
  if(r==255)break;
 }
 reset();read_result=-ETIMEDOUT;assert(hub_supply_enable()==-ETIMEDOUT);
 reset();read_result=4;assert(hub_supply_enable()==-EIO&&logs==1);
 reset();read_value=0x40;assert(hub_supply_enable()==-EIO);
 reset();assert(mcu_power_show(0,0,buffer)==2&&buffer[0]=='1');
 reset();read_value=0;assert(mcu_power_show(0,0,buffer)==2&&buffer[0]=='0');
 reset();read_result=-ENODEV;assert(mcu_power_show(0,0,buffer)==-ENODEV);
 reset();read_result=7;assert(mcu_power_show(0,0,buffer)==-EIO);
 reset();assert(mcu_power_store(0,0,"0",1)==1&&updates==0&&reads==0);
 reset();assert(mcu_power_store(0,0,"bad",3)==-EINVAL&&updates==0);
 reset();assert(mcu_power_store(0,0,"1",1)==1&&updates==1&&reads==1);
 reset();update_results[0]=3;assert(mcu_power_store(0,0,"1",1)==-EIO&&reads==0);
 reset();read_result=-ETIMEDOUT;assert(mcu_power_store(0,0,"1",1)==-ETIMEDOUT);
 reset();read_value=0;assert(mcu_power_store(0,0,"1",1)==-EIO);
 reset();assert(hub_cycle(1000)==0&&parks==1&&restores==1&&enabled==1&&disabled==1&&updates==2&&reads==2&&parked_cs_inactive);
 reset();update_results[0]=9;assert(hub_cycle(1000)==-EIO&&parks==0&&restores==0&&enabled==0&&disabled==0);
 reset();read_result=-ETIMEDOUT;assert(hub_cycle(1000)==-ETIMEDOUT&&parks==0&&restores==0&&enabled==0);
 reset();update_results[1]=-EIO;assert(hub_cycle(1000)==-EIO&&parks==1&&disabled==1&&enabled==0&&parked_cs_inactive);
 reset();later_read_result=-ETIMEDOUT;assert(hub_cycle(1000)==-ETIMEDOUT&&parks==1&&disabled==1&&enabled==0);
 reset();restore_result=-EIO;assert(hub_cycle(1000)==-EIO&&enabled==0);
 reset();supply_cut=true;assert(hub_cycle(1000)==0&&updates==2&&update_values[0]==0&&update_values[1]==0xc0&&enabled==1&&!parked_cs_inactive);
 reset();supply_cut=true;update_results[0]=2;assert(hub_cycle(1000)==-EIO&&updates==1&&reads==0&&sleeps==0&&enabled==0);
 reset();supply_cut=true;update_results[1]=-ETIMEDOUT;assert(hub_cycle(1000)==-ETIMEDOUT&&updates==2&&restores==0&&enabled==0);
 return 0;
}
'''


class SensorPowerErrors(unittest.TestCase):
    def test_actual_c_checks_acpm_failures_and_readback_before_releasing_hub(self):
        cc=shutil.which('cc')
        if not cc:self.skipTest('C compiler unavailable')
        text=SOURCE.read_text()
        body='\n'.join(function(text,n) for n in ['hub_pmic_result','hub_supply_enable','mcu_power_show','mcu_power_store','hub_cycle'])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'power.c').write_text(STUB+body+CASES)
            subprocess.run([cc,'-std=c99','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(p/'power.c'),'-o',str(p/'power')],check=True)
            subprocess.run([str(p/'power')],check=True)


if __name__=='__main__':unittest.main()

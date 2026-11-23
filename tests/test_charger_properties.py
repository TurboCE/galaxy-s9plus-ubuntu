# SPDX-License-Identifier: GPL-2.0-only
"""Execute the driver's actual C property functions against a faultable regmap."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    import re
    match = re.search(r'^static [^\n]+\b' + name + r'\(', source, re.M)
    if not match:
        raise AssertionError(name)
    start = source.index('{', match.start())
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end] + '\n'


PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <limits.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <stddef.h>
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
struct mutex { bool held; };
static void mutex_lock(struct mutex *m) { assert(!m->held);m->held=true; }
static void mutex_unlock(struct mutex *m) { assert(m->held);m->held=false; }
#define BIT(n) (1U << (n))
#define clamp_t(t,v,lo,hi) ((t)(v) < (t)(lo) ? (t)(lo) : (t)(v) > (t)(hi) ? (t)(hi) : (t)(v))
#define dev_dbg(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_err(...) ((void)0)
#define msleep(...) ((void)0)
#define IRQ_HANDLED 1
#define AICL_WORK_DELAY_MS 100
#define MAX77705_AICL_I 7
#define MAX77705_CHG_DISABLE 0
#define MAX77705_CURRENT_CHGIN_MIN 100000
#define MAX77705_CURRENT_CHGIN_MAX 3200000
#define MAX77705_CURRENT_CHGIN_STEP 25000
#define MAX77705_CURRENT_CHG_STEP 50000
#define MAX77705_CURRENT_CHG_MAX (63 * MAX77705_CURRENT_CHG_STEP)
#define MAX77705_CHG_REG_INT_OK 0xb2
#define MAX77705_CHG_REG_DETAILS_00 0xb3
#define MAX77705_CHG_REG_DETAILS_01 0xb4
#define MAX77705_CHG_REG_CNFG_00 0xb7
#define MAX77705_CHG_REG_CNFG_02 0xb9
#define MAX77705_CHG_REG_CNFG_04 0xbb
#define MAX77705_CHG_REG_CNFG_09 0xc0
#define MAX77705_BATP_OK BIT(2)
#define MAX77705_CHGIN_OK BIT(6)
#define MAX77705_BATP_DTLS BIT(0)
#define MAX77705_CHGIN_DTLS 0x60
#define MAX77705_CHGIN_DTLS_SHIFT 5
#define MAX77705_CHG_DTLS 0xf
#define MAX77705_BAT_DTLS 0x70
#define MAX77705_BAT_DTLS_SHIFT 4
#define MAX77705_CHARGER_CONSTANT_CURRENT 1
#define MAX77705_CHARGER_CONSTANT_VOLTAGE 2
#define MAX77705_CHARGER_END_OF_CHARGE 3
#define MAX77705_CHARGER_DONE 4
#define MAX77705_BATTERY_NOBAT 0
#define MAX77705_BATTERY_PREQUALIFICATION 1
#define MAX77705_BATTERY_DEAD 2
#define MAX77705_BATTERY_GOOD 3
#define MAX77705_BATTERY_LOWVOLTAGE 4
#define MAX77705_BATTERY_OVERVOLTAGE 5
#define REG_FIELD(r,l,m) { .reg=(r), .lsb=(l), .msb=(m) }
typedef int irqreturn_t;
struct reg_field { unsigned int reg, lsb, msb; };
enum max77705_field_idx { MAX77705_CHG_EN, MAX77705_CHG_CC_LIM, MAX77705_CHG_CHGIN_LIM, MAX77705_CHG_CV_PRM, N_FIELDS };
static const struct reg_field max77705_reg_field[] = {
 [MAX77705_CHG_EN] = REG_FIELD(MAX77705_CHG_REG_CNFG_09,7,7),
 [MAX77705_CHG_CC_LIM] = REG_FIELD(MAX77705_CHG_REG_CNFG_02,0,5),
 [MAX77705_CHG_CHGIN_LIM] = REG_FIELD(MAX77705_CHG_REG_CNFG_09,0,6),
 [MAX77705_CHG_CV_PRM] = REG_FIELD(MAX77705_CHG_REG_CNFG_04,0,5),
};
struct regmap { unsigned int regs[256]; int reads, writes, fail_read, fail_write; unsigned int last_written; bool aicl_after_write, ignore_write; };
struct regmap_field { struct regmap *map; struct reg_field field; };
struct power_supply_battery_info { int voltage_max_design_uv, constant_charge_voltage_max_uv; };
struct max77705_charger_data { struct regmap *regmap; struct regmap_field *rfield[N_FIELDS]; void *dev; struct power_supply_battery_info *bat_info; };
struct power_supply { struct max77705_charger_data *data; };
union power_supply_propval { int intval; const char *strval; };
enum power_supply_property { POWER_SUPPLY_PROP_ONLINE, POWER_SUPPLY_PROP_PRESENT, POWER_SUPPLY_PROP_STATUS, POWER_SUPPLY_PROP_CHARGE_TYPE, POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR, POWER_SUPPLY_PROP_HEALTH, POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT, POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT, POWER_SUPPLY_PROP_CONSTANT_CHARGE_VOLTAGE, POWER_SUPPLY_PROP_VOLTAGE_MAX_DESIGN, POWER_SUPPLY_PROP_MODEL_NAME, POWER_SUPPLY_PROP_MANUFACTURER };
enum { POWER_SUPPLY_STATUS_UNKNOWN=0, POWER_SUPPLY_STATUS_CHARGING=1, POWER_SUPPLY_STATUS_DISCHARGING=2, POWER_SUPPLY_STATUS_NOT_CHARGING=3, POWER_SUPPLY_STATUS_FULL=4 };
enum { POWER_SUPPLY_CHARGE_TYPE_NONE=1, POWER_SUPPLY_CHARGE_TYPE_FAST=3 };
enum { POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO=0, POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE=1 };
enum { POWER_SUPPLY_HEALTH_GOOD=1, POWER_SUPPLY_HEALTH_DEAD=3, POWER_SUPPLY_HEALTH_OVERVOLTAGE=4, POWER_SUPPLY_HEALTH_UNSPEC_FAILURE=5, POWER_SUPPLY_HEALTH_UNDERVOLTAGE=12, POWER_SUPPLY_HEALTH_NO_BATTERY=15 };
static const char *max77705_charger_model="test", *max77705_charger_manufacturer="test";
static struct max77705_charger_data *power_supply_get_drvdata(struct power_supply *p) { return p->data; }
static int regmap_read(struct regmap *m,unsigned int reg,unsigned int *v) {
 m->reads++; if(m->fail_read==m->reads)return -EIO;
 *v=m->regs[reg]; if(reg==MAX77705_CHG_REG_INT_OK && m->aicl_after_write && m->writes)*v|=BIT(7); return 0;
}
static int regmap_field_read(struct regmap_field *f,unsigned int *v) {
 unsigned int raw;int r=regmap_read(f->map,f->field.reg,&raw);if(r)return r;
 *v=(raw>>f->field.lsb)&((1U<<(f->field.msb-f->field.lsb+1))-1);return 0;
}
static int regmap_field_write(struct regmap_field *f,unsigned int v) {
 struct regmap *m=f->map; if(m->fail_write)return -EIO;
 unsigned int mask=((1U<<(f->field.msb-f->field.lsb+1))-1)<<f->field.lsb;
 m->last_written=v;m->writes++;if(m->ignore_write)return 0;m->regs[f->field.reg]=(m->regs[f->field.reg]&~mask)|((v<<f->field.lsb)&mask);return 0;
}
'''

TESTS = r'''
static struct regmap m;
static struct max77705_charge_policy policy;
#define chg policy.hw
static struct regmap_field fields[N_FIELDS];
static struct power_supply psy;
static struct power_supply_battery_info bat={4400000,4350000};
static void setup(void) {
 memset(&m,0,sizeof m);memset(&policy,0,sizeof policy);policy.requested=true;policy.ready=true;chg.regmap=&m;chg.bat_info=&bat;psy.data=&chg;
 for(int i=0;i<N_FIELDS;i++){fields[i]=(struct regmap_field){&m,max77705_charger_reg_field(i)};chg.rfield[i]=&fields[i];}
 m.regs[MAX77705_CHG_REG_CNFG_00]=5;m.regs[MAX77705_CHG_REG_CNFG_09]=0x93;
 m.regs[MAX77705_CHG_REG_INT_OK]=MAX77705_BATP_OK|MAX77705_CHGIN_OK;
 m.regs[MAX77705_CHG_REG_DETAILS_00]=3<<5;
 m.regs[MAX77705_CHG_REG_DETAILS_01]=(MAX77705_BATTERY_GOOD<<4)|MAX77705_CHARGER_CONSTANT_CURRENT;
}
static void currents(void) {
 int requests[]={INT_MIN,-1,0,99999,100000,125000,499999,500000,3199999,3200000,INT_MAX};
 int expected[]={100000,100000,100000,100000,100000,125000,475000,500000,3175000,3200000,3200000};
 for(unsigned i=0;i<sizeof(requests)/sizeof(*requests);i++){
  setup();union power_supply_propval v={.intval=requests[i]},out={0};
  assert(max77705_set_property(&psy,POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT,&v)==0);
  assert(m.last_written<=127);assert(m.regs[MAX77705_CHG_REG_CNFG_09]&0x80);
  assert(max77705_chg_get_property(&psy,POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT,&out)==0);assert(out.intval==expected[i]);
 }
 int cc_requests[]={INT_MIN,-1,0,100000,900000,3150000,3200000,INT_MAX};
 int cc_expected[]={100000,100000,100000,100000,900000,3150000,3150000,3150000};
 for(unsigned i=0;i<sizeof(cc_requests)/sizeof(*cc_requests);i++){
  setup();m.regs[MAX77705_CHG_REG_CNFG_02]=0xc0;union power_supply_propval v={.intval=cc_requests[i]},out={0};
  assert(max77705_set_property(&psy,POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT,&v)==0);
  assert(m.last_written<=63);assert((m.regs[MAX77705_CHG_REG_CNFG_02]&0xc0)==0xc0);
  assert(max77705_chg_get_property(&psy,POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT,&out)==0);assert(out.intval==cc_expected[i]);
 }
 setup();assert(max77705_set_integer(&chg,MAX77705_CHG_CHGIN_LIM,1,2,0,1)==-EINVAL);
 assert(max77705_set_integer(&chg,MAX77705_CHG_CHGIN_LIM,2,1,1,1)==-EINVAL);
 assert(max77705_set_integer(&chg,MAX77705_CHG_CHGIN_LIM,1,UINT_MAX,1,1)==-EINVAL);
 assert(max77705_set_integer(&chg,MAX77705_CHG_CHGIN_LIM,1,2,25000,1)==-EINVAL);assert(m.writes==0);
}
static void status(void) {
 setup();union power_supply_propval v={.intval=POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE},out={0};
 assert(max77705_set_property(&psy,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==0);
 assert(m.regs[MAX77705_CHG_REG_CNFG_00]==4);assert(m.regs[MAX77705_CHG_REG_CNFG_09]==0x93);
 assert(max77705_chg_get_property(&psy,POWER_SUPPLY_PROP_STATUS,&out)==0);assert(out.intval==POWER_SUPPLY_STATUS_NOT_CHARGING);
 assert(max77705_chg_get_property(&psy,POWER_SUPPLY_PROP_CHARGE_TYPE,&out)==0);assert(out.intval==POWER_SUPPLY_CHARGE_TYPE_NONE);
 assert(max77705_chg_get_property(&psy,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&out)==0);assert(out.intval==POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE);
 v.intval=POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO;assert(max77705_set_property(&psy,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==0);
 assert(m.regs[MAX77705_CHG_REG_CNFG_00]==5);assert(m.regs[MAX77705_CHG_REG_CNFG_09]==0x93);
 int raw[]={1,2,3,4,7,8,15};int expected[]={1,1,4,4,3,2,0};
 for(unsigned i=0;i<sizeof(raw)/sizeof(*raw);i++){m.regs[MAX77705_CHG_REG_DETAILS_01]=raw[i];assert(max77705_get_status(&chg,&out.intval)==0);assert(out.intval==expected[i]);}
 m.regs[MAX77705_CHG_REG_DETAILS_01]=MAX77705_BATTERY_PREQUALIFICATION<<4;out.intval=-999;
 assert(max77705_get_battery_health(&chg,&out.intval)==0);assert(out.intval==POWER_SUPPLY_HEALTH_GOOD);
}
static void errors(void) {
 int props[]={POWER_SUPPLY_PROP_ONLINE,POWER_SUPPLY_PROP_PRESENT,POWER_SUPPLY_PROP_STATUS,POWER_SUPPLY_PROP_CHARGE_TYPE,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,POWER_SUPPLY_PROP_HEALTH,POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT,POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT,POWER_SUPPLY_PROP_CONSTANT_CHARGE_VOLTAGE};
 int reads[]={1,2,2,2,1,3,1,1,1};
 for(unsigned i=0;i<sizeof(props)/sizeof(*props);i++)for(int fail=1;fail<=reads[i];fail++){
  setup();m.fail_read=fail;union power_supply_propval out={.intval=0x6b6b};assert(max77705_chg_get_property(&psy,props[i],&out)==-EIO);
 }
 for(int i=0;i<4;i++){
  setup();m.fail_write=1;union power_supply_propval v={.intval=i==0?500000:i==1?900000:i==2?0:1};
  int prop=i==0?POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT:i==1?POWER_SUPPLY_PROP_CONSTANT_CHARGE_CURRENT:POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR;
  assert(max77705_set_property(&psy,prop,&v)==-EIO);
 }
}
static void aicl(void) {
 for(unsigned reg=0;reg<=3;reg++){
  setup();m.regs[MAX77705_CHG_REG_INT_OK]=0;m.regs[MAX77705_CHG_REG_CNFG_09]=0x80|reg;
  assert(max77705_aicl_irq(0,&chg)==IRQ_HANDLED);assert(m.writes==0);assert(m.regs[MAX77705_CHG_REG_CNFG_09]==(0x80|reg));
 }
 setup();m.regs[MAX77705_CHG_REG_INT_OK]=0;m.regs[MAX77705_CHG_REG_CNFG_09]=0x84;m.aicl_after_write=true;
 assert(max77705_aicl_irq(0,&chg)==IRQ_HANDLED);assert(m.writes==1);assert(m.regs[MAX77705_CHG_REG_CNFG_09]==0x83);
}
static void mapping(void) {
 struct reg_field f=max77705_charger_reg_field(MAX77705_CHG_EN);assert(f.reg==0xb7&&f.lsb==0&&f.msb==0);
 f=max77705_charger_reg_field(MAX77705_CHG_CHGIN_LIM);assert(f.reg==0xc0&&f.lsb==0&&f.msb==6);
 f=max77705_charger_reg_field(MAX77705_CHG_CC_LIM);assert(f.reg==0xb9&&f.lsb==0&&f.msb==5);
}
static void policy_cas(void) {
 setup();assert(max77705_set_policy_allow(&chg,0,false)==0);
 assert(policy.requested && policy.policy_blocked && policy.request_generation==0);
 assert(!(m.regs[MAX77705_CHG_REG_CNFG_00]&1));
 assert(max77705_set_charge_request(&chg,true)==0); /* User auto cannot bypass policy. */
 assert(policy.requested && policy.request_generation==1 && !(m.regs[MAX77705_CHG_REG_CNFG_00]&1));
 int writes=m.writes;assert(max77705_set_policy_allow(&chg,0,true)==-EAGAIN);assert(m.writes==writes);
 assert(max77705_set_policy_allow(&chg,1,true)==0);assert(m.regs[MAX77705_CHG_REG_CNFG_00]&1);
 assert(max77705_set_charge_request(&chg,false)==0);assert(!policy.requested);
 writes=m.writes;assert(max77705_set_policy_allow(&chg,1,true)==-EAGAIN);assert(m.writes==writes);
 assert(max77705_set_policy_allow(&chg,2,true)==0);assert(!(m.regs[MAX77705_CHG_REG_CNFG_00]&1));
 setup();m.ignore_write=true;assert(max77705_set_policy_allow(&chg,0,false)==-EIO);assert(policy.policy_blocked);
 setup();m.fail_read=1;assert(max77705_set_policy_allow(&chg,0,true)==-EIO);assert(policy.policy_blocked);assert(!(m.regs[MAX77705_CHG_REG_CNFG_00]&1));
 setup();policy.ready=false;assert(max77705_set_policy_allow(&chg,0,true)==-EAGAIN);assert(!m.writes);
}

static void intent(void) {
 policy_cas();
 struct power_supply_battery_info info={4400000,4350000};
 assert(max77705_initial_float_voltage(&info)==4350000);
 info.constant_charge_voltage_max_uv=-EINVAL;assert(max77705_initial_float_voltage(&info)==4200000);
 info.voltage_max_design_uv=4100000;assert(max77705_initial_float_voltage(&info)==4100000);
 info.constant_charge_voltage_max_uv=4350000;assert(max77705_initial_float_voltage(&info)==4100000);
 info.voltage_max_design_uv=3900000;assert(max77705_initial_float_voltage(&info)==-EINVAL);
 info.voltage_max_design_uv=-EINVAL;info.constant_charge_voltage_max_uv=4500001;assert(max77705_initial_float_voltage(&info)==-EINVAL);
 setup();m.ignore_write=true;assert(max77705_set_charge_request(&chg,false)==-EIO);assert(policy.requested);assert(!policy.lock.held);
 setup();m.fail_read=1;assert(max77705_set_charge_request(&chg,false)==-EIO);assert(policy.requested);assert(!(m.regs[MAX77705_CHG_REG_CNFG_00]&1));
 setup();policy.ready=false;assert(max77705_set_charge_request(&chg,false)==-EAGAIN);assert(m.writes==0);assert(policy.requested);assert(!policy.lock.held);
 setup();unsigned int before=m.regs[MAX77705_CHG_REG_CNFG_00];
 assert(max77705_set_charge_request(&chg,false)==0);assert(!policy.requested);
 assert(m.regs[MAX77705_CHG_REG_CNFG_00]==(before&~1U));
 m.fail_write=1;assert(max77705_set_charge_request(&chg,true)==-EIO);assert(!policy.requested);assert(!policy.lock.held);
 m.fail_write=0;assert(max77705_set_charge_request(&chg,true)==0);assert(policy.requested);
 m.regs[MAX77705_CHG_REG_CNFG_00]&=~1U; /* Hardware changed after accepted request. */
 assert(policy.requested);int status;assert(max77705_get_status(&chg,&status)==0);assert(status==POWER_SUPPLY_STATUS_NOT_CHARGING);
 union power_supply_propval value={.intval=POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE};
 assert(max77705_set_property(&psy,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&value)==0);assert(!policy.requested);
 m.fail_write=1;value.intval=POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO;
 assert(max77705_set_property(&psy,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&value)==-EIO);assert(!policy.requested);
}
int main(int argc,char **argv){assert(argc==2);if(!strcmp(argv[1],"currents"))currents();else if(!strcmp(argv[1],"status"))status();else if(!strcmp(argv[1],"errors"))errors();else if(!strcmp(argv[1],"aicl"))aicl();else if(!strcmp(argv[1],"mapping"))mapping();else if(!strcmp(argv[1],"intent"))intent();else return 2;return 0;}
'''


@unittest.skipUnless(shutil.which('cc'), 'C compiler required')
class ChargerPropertiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        directory = Path(cls.temporary.name)
        source = (ROOT / 'src/soc/max77705_charger.c').read_text()
        names = ['charge_policy', 'max77705_set_policy_allow', 'max77705_initial_float_voltage', 'max77705_set_charge_request',
                 'max77705_aicl_irq', 'max77705_charger_enable', 'max77705_get_online',
                 'max77705_charger_reg_field', 'max77705_set_integer', 'max77705_check_battery',
                 'max77705_get_charge_type', 'max77705_get_status', 'max77705_get_vbus_state',
                 'max77705_get_battery_health', 'max77705_get_health', 'max77705_get_input_current',
                 'max77705_get_charge_current', 'max77705_get_float_voltage',
                 'max77705_chg_get_property', 'max77705_set_property']
        harness = directory / 'charger.c'
        start = source.index('struct max77705_charge_policy {')
        policy_struct = source[start:source.index('};', start)+2]
        harness.write_text(PRELUDE + policy_struct + '\n'.join(function(source, n) for n in names) + TESTS)
        cls.binary = directory / 'charger'
        subprocess.run(['cc', '-std=gnu11', '-Werror', str(harness), '-o', str(cls.binary)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_case(self, name):
        subprocess.run([str(self.binary), name], check=True, timeout=5)

    def test_current_round_trips_extremes_and_preserves_neighbor_bits(self):
        self.run_case('currents')

    def test_charge_state_uses_status_enum_and_actual_charge_enable(self):
        self.run_case('status')

    def test_property_io_errors_are_returned(self):
        self.run_case('errors')

    def test_aicl_cannot_underflow_minimum_into_maximum(self):
        self.run_case('aicl')

    def test_register_mapping_does_not_repurpose_input_control(self):
        self.run_case('mapping')

    def test_intent_survives_hardware_drop_and_rejects_failed_policy_writes(self):
        self.run_case('intent')


class ChargerSourceGuardTests(unittest.TestCase):
    def check_guard(self, data):
        script = (ROOT / 'scripts/build/apply_drivers.sh').read_text()
        guard = script[script.index('ref="$PROJ/src/reference/max77705_charger.c"'):
                       script.index('install -m644 "$PROJ/src/soc/max77705_charger.c"')]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            for relative in ['src/reference', 'src/soc', 'kernel/drivers/power/supply']:
                (base / relative).mkdir(parents=True)
            shutil.copyfile(ROOT / 'src/reference/max77705_charger.c', base / 'src/reference/max77705_charger.c')
            shutil.copyfile(ROOT / 'src/soc/max77705_charger.c', base / 'src/soc/max77705_charger.c')
            (base / 'kernel/drivers/power/supply/max77705_charger.c').write_bytes(data)
            return subprocess.run(['bash', '-c', guard], env=dict(os.environ, PROJ=str(base), SRC=str(base/'kernel')),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode

    def test_pristine_and_exact_current_source_are_accepted(self):
        for file in ['src/reference/max77705_charger.c', 'src/soc/max77705_charger.c']:
            self.assertEqual(self.check_guard((ROOT/file).read_bytes()), 0)

    def test_unexpected_source_drift_is_rejected(self):
        self.assertNotEqual(self.check_guard((ROOT/'src/soc/max77705_charger.c').read_bytes()+b'\n/* unexpected */\n'), 0)

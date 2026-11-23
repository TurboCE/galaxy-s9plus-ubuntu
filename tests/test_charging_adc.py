# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual ADC C conversion/IRQ paths with faultable clock and MMIO."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from test_charger_properties import function

ROOT = Path(__file__).resolve().parents[1]
PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <string.h>
#define __iomem
#define BIT(n) (1U << (n))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define IIO_CHAN_INFO_RAW 0
#define IIO_VAL_INT 1
#define IRQ_NONE 0
#define IRQ_HANDLED 1
typedef uint32_t u32;
typedef int irqreturn_t;
struct clk { int unused; };
struct mutex { bool held; };
struct completion { int count; };
struct iio_dev { void *priv; };
struct iio_chan_spec { unsigned int address; };
static void *iio_priv(struct iio_dev *d) { return d->priv; }
static void mutex_lock(struct mutex *m) { assert(!m->held);m->held=true; }
static void mutex_unlock(struct mutex *m) { assert(m->held);m->held=false; }
static void reinit_completion(struct completion *c) { c->count=0; }
static void complete(struct completion *c) { c->count++; }
static u32 registers[64];
static bool powered, irq_enabled;
static int clock_error, writes, simulation;
static int clk_prepare_enable(struct clk *c) {
 assert(!powered);if(clock_error)return clock_error;powered=true;return 0;
}
static int readl(void *p) {
 assert(powered);assert(p>=(void *)registers && p<(void *)(registers+64));
 return *(u32 *)p;
}
static void writel(u32 value,void *p) {
 assert(powered);assert(p>=(void *)registers && p<(void *)(registers+64));writes++;
 if(p==(void *)((char *)registers+0x14))*(u32 *)p&=~value;else *(u32 *)p=value;
}
static void enable_irq(int irq) { assert(powered&&!irq_enabled);irq_enabled=true; }
static void disable_irq(int irq) { assert(powered&&irq_enabled);irq_enabled=false; }
static void clk_disable_unprepare(struct clk *c) { assert(powered&&!irq_enabled);powered=false; }
static unsigned long msecs_to_jiffies(unsigned long ms) { return ms; }
static unsigned long wait_for_completion_timeout(struct completion *,unsigned long);
'''
WAIT = r'''
static struct g965n_adc adc;
static unsigned long wait_for_completion_timeout(struct completion *c,unsigned long ms) {
 assert(ms==100&&powered&&irq_enabled&&adc.pending);
 assert(registers[ADC_INT_EN/4]==1);
 assert(registers[ADC_CON1/4]==(ADC_NON_RESET|ADC_START));
 assert((registers[ADC_CON2/4]&ADC_TIME_MASK)==ADC_TIME);
 if(simulation==0)return 0;
 if(simulation==2){assert(g965n_adc_irq(1,&adc)==IRQ_NONE);assert(!c->count);assert(adc.pending);}
 registers[ADC_DATA/4]=0x80000abc;registers[ADC_INT_ST/4]=1;
 assert(g965n_adc_irq(1,&adc)==IRQ_HANDLED);assert(c->count==1&&!adc.pending);
 registers[ADC_DATA/4]=0x321;registers[ADC_INT_ST/4]=1;
 assert(g965n_adc_irq(1,&adc)==IRQ_HANDLED);assert(c->count==1&&adc.value==0xabc);
 return 1;
}
'''
TEST = r'''
static void setup(void) {
 memset(&adc,0,sizeof adc);memset(registers,0,sizeof registers);
 adc.regs=registers;adc.irq=1;powered=false;irq_enabled=false;clock_error=0;writes=0;simulation=1;
}
static int sample(unsigned int channel,int *value,int *value2,long mask) {
 struct iio_dev dev={&adc};struct iio_chan_spec chan={channel};
 int ret=g965n_adc_read_raw(&dev,&chan,value,value2,mask);
 assert(!powered&&!irq_enabled&&!adc.lock.held&&!adc.pending);
 return ret;
}
int main(void) {
 int v,v2;
 unsigned int channels[]={1,3,4,11};
 for(unsigned int i=0;i<4;i++){
  setup();v=0;v2=99;assert(sample(channels[i],&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT);
  assert(v==0xabc&&v2==0);assert(registers[ADC_CON2/4]==0);
  assert(!(registers[ADC_CON2/4]&ADC_TIME_MASK));assert(registers[ADC_INT_EN/4]==0);assert(!(registers[ADC_CON1/4]&ADC_START));
 }
 for(unsigned int i=0;i<20;i++)if(!g965n_adc_channel_valid(i)){
  setup();v=123;v2=456;assert(sample(i,&v,&v2,IIO_CHAN_INFO_RAW)==-EINVAL);assert(!writes&&v==123&&v2==456);
 }
 setup();v=123;v2=456;assert(sample(4,&v,&v2,999)==-EINVAL);assert(!writes);
 setup();clock_error=-EIO;assert(sample(4,&v,&v2,IIO_CHAN_INFO_RAW)==-EIO);assert(!writes&&v==123&&v2==456);
 setup();registers[ADC_INT_EN/4]=1;assert(sample(4,&v,&v2,IIO_CHAN_INFO_RAW)==-EBUSY);assert(!writes&&registers[ADC_INT_EN/4]==1);
 setup();registers[ADC_CON1/4]=ADC_START;assert(sample(4,&v,&v2,IIO_CHAN_INFO_RAW)==-EBUSY);assert(!writes&&registers[ADC_CON1/4]==ADC_START);
 setup();simulation=0;v=123;v2=456;assert(sample(4,&v,&v2,IIO_CHAN_INFO_RAW)==-ETIMEDOUT);assert(v==123&&v2==456);assert(!registers[ADC_INT_EN/4]);
 simulation=2;assert(sample(4,&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT);assert(v==0xabc&&v2==0);
 setup();simulation=2;assert(sample(1,&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT);assert(v==0xabc);
 return 0;
}
'''


@unittest.skipUnless(shutil.which('cc'), 'C compiler required')
class ChargingAdcTests(unittest.TestCase):
    def test_actual_conversion_errors_irq_ownership_and_clock_cleanup(self):
        source = (ROOT/'experiments/charging/g965n-adc-v3.c').read_text()
        defines = '\n'.join(re.findall(r'^#define ADC_.*$', source, re.M))
        start = source.index('struct g965n_adc {')
        structure = source[start:source.index('};', start)+2]
        funcs = '\n'.join(function(source, n) for n in (
            'g965n_adc_channel_valid', 'g965n_adc_hw_init',
            'g965n_adc_hw_stop', 'g965n_adc_irq'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'actual-adc.c'
            path.write_text(PRELUDE+defines+'\n'+structure+'\n'+funcs+WAIT+
                            function(source, 'g965n_adc_read_raw')+TEST)
            binary = Path(directory)/'actual-adc'
            subprocess.run(['cc', '-std=gnu11', '-Werror', '-fsanitize=address,undefined',
                            str(path), '-o', str(binary)], check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=5)

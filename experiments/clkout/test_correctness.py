#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual new provider and generic gate/mux operations against fake MMIO."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SPEC=importlib.util.spec_from_file_location('clkout_apply',HERE/'apply.py')
A=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(A)
M=json.loads((HERE/'SOURCES.json').read_text())
FIXTURE=Path(os.environ.get('CLKOUT_FIXTURE',str(ROOT/'.local/context/clkout-pristine')))


def function(text,name):
    match=re.search(r'(?m)^static [^;{}]*?\b'+name+r'\([^;{}]*\)\s*\{',text)
    assert match,name
    pos=match.end();depth=1
    while depth:
        depth+=(text[pos]=='{')-(text[pos]=='}');pos+=1
    return text[match.start():pos]


STUB=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;typedef uint32_t u32;typedef int spinlock_t;
#define __iomem
#define GFP_KERNEL 0
#define ENOMEM 12
#define ENODEV 19
#define EPROBE_DEFER 517
#define CLK_GATE_SET_TO_DISABLE 1
#define CLK_GATE_HIWORD_MASK 2
#define CLK_MUX_HIWORD_MASK 4
#define CLK_SET_RATE_PARENT 1
#define CLK_SET_RATE_NO_REPARENT 2
#define CLK_IGNORE_UNUSED 4
#define BIT(n) (1U<<(n))
#define struct_size(p,member,n) (sizeof(*(p))+sizeof((p)->member[0])*(n))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define __acquire(x) ((void)0)
#define __release(x) ((void)0)
#define spin_lock_init(p) (*(p)=0)
#define spin_lock_irqsave(p,f) do {assert(!*(p));*(p)=1;(f)=0;} while(0)
#define spin_unlock_irqrestore(p,f) do {assert(*(p));*(p)=0;(void)(f);} while(0)
struct device_node {bool is9810;};
struct device {struct device *parent;struct device_node *of_node;void *data;};
struct platform_device {struct device dev;};
struct clk {const char *name;};struct clk_hw {int id;};struct clk_ops {int dummy;};
struct clk_gate {struct clk_hw hw;void *reg;u8 bit_idx;u8 flags;spinlock_t *lock;};
struct clk_mux {struct clk_hw hw;void *reg;u32 mask;u8 shift;u8 flags;u32 *table;spinlock_t *lock;};
struct clk_hw_onecell_data {unsigned num;struct clk_hw *hws[];};
static struct clk_ops clk_gate_ops,clk_mux_ops;
static struct clk clocks[2]={{"tcxo0"},{"tcxo1"}};
static struct clk_hw hw[2];
static u32 mmio[0x1000/4];
static void *allocations[8];static int nalloc,failalloc,failparent,failmap,failreg,failprovider;
static int gets,puts,maps,unmaps,attempts,registered,unregistered,provider,delprovider,writes;
static int unreg_order[2];
static bool of_device_is_compatible(struct device_node *n,const char *s) {return n&&n->is9810&&!strcmp(s,"samsung,exynos9810-pmu");}
static void *devm_kzalloc(struct device *d,size_t n,int flags) {nalloc++;if(nalloc==failalloc)return NULL;return allocations[nalloc-1]=calloc(1,n);}
static struct clk *of_clk_get_by_name(struct device_node *n,const char *s) {int i=!strcmp(s,"clkout1");if(i==failparent)return ERR_PTR(-EPROBE_DEFER);gets++;return &clocks[i];}
static const char *__clk_get_name(struct clk *c) {return c->name;}
static void clk_put(struct clk *c) {assert(c==&clocks[0]||c==&clocks[1]);puts++;}
static void *of_iomap(struct device_node *n,int idx) {if(failmap)return NULL;maps++;return mmio;}
static void iounmap(void *p) {assert(p==mmio);unmaps++;}
static struct clk_hw *clk_hw_register_composite(struct device *d,const char *name,const char *const *parents,int count,struct clk_hw *mux,const struct clk_ops *mops,struct clk_hw *rate,const struct clk_ops *rops,struct clk_hw *gate,const struct clk_ops *gops,unsigned long flags) {
 int index=attempts++;assert(count==64&&flags==(CLK_SET_RATE_PARENT|CLK_SET_RATE_NO_REPARENT|CLK_IGNORE_UNUSED));
 assert(!rate&&!rops&&mops==&clk_mux_ops&&gops==&clk_gate_ops);
 if(index==failreg)return ERR_PTR(-71);hw[index].id=index;registered++;return &hw[index];
}
static void clk_hw_unregister_composite(struct clk_hw *p) {unreg_order[unregistered++]=p->id;}
static void *of_clk_hw_onecell_get;
static int of_clk_add_hw_provider(struct device_node *n,void *getter,struct clk_hw_onecell_data *d) {assert(d->num==2);if(failprovider)return -72;provider++;return 0;}
static void of_clk_del_provider(struct device_node *n) {delprovider++;}
static void platform_set_drvdata(struct platform_device *p,void *d) {p->dev.data=d;}
static void *platform_get_drvdata(struct platform_device *p) {return p->dev.data;}
static void *dev_get_drvdata(struct device *d) {return d->data;}
static u32 readl(void *p) {assert((char *)p>=(char *)mmio&&(char *)p<(char *)(mmio+0x400));return *(u32 *)p;}
static void writel(u32 v,void *p) {assert((char *)p>=(char *)mmio&&(char *)p<(char *)(mmio+0x400));writes++;*(u32 *)p=v;}
#define to_clk_gate(p) container_of(p,struct clk_gate,hw)
#define to_clk_mux(p) container_of(p,struct clk_mux,hw)
static u32 clk_gate_readl(struct clk_gate *g) {return readl(g->reg);}
static void clk_gate_writel(struct clk_gate *g,u32 v) {writel(v,g->reg);}
static u32 clk_mux_readl(struct clk_mux *m) {return readl(m->reg);}
static void clk_mux_writel(struct clk_mux *m,u32 v) {writel(v,m->reg);}
static u32 clk_mux_index_to_val(u32 *table,u8 flags,u8 index) {assert(!table&&!flags);return index;}
'''
CASES=r'''
static void reset(void) {
 for(int i=0;i<8;i++){free(allocations[i]);allocations[i]=NULL;}
 nalloc=failalloc=failmap=failprovider=0;failparent=failreg=-1;
 gets=puts=maps=unmaps=attempts=registered=unregistered=provider=delprovider=writes=0;
 for(int i=0;i<0x400;i++)mmio[i]=0xa5a5a5a5U;
}
int main(void) {
 struct device_node node={true};struct device parent={.of_node=&node};struct platform_device p={.dev.parent=&parent};
 reset();assert(exynos9810_clkout_device(&p.dev));assert(exynos9810_clkout_probe(&p)==0);
 struct exynos9810_clkout *out=p.dev.data;
 assert(registered==2&&gets==2&&provider==1&&writes==0); /* Probe preserves inherited registers. */
 for(unsigned i=0;i<2;i++) {
  unsigned slot=i?0:1;
  assert(out->gates[i].reg==(char *)out->reg+(i?0xa0c:0xa00));
  assert(out->gates[i].bit_idx==0&&out->gates[i].flags==CLK_GATE_SET_TO_DISABLE);
  assert(out->muxes[i].mask==63&&out->muxes[i].shift==8);
  assert(out->gates[i].lock==&out->lock&&out->muxes[i].lock==&out->lock);
  for(unsigned j=0;j<64;j++)assert(!strcmp(out->parent_names[i][j],j==slot?clocks[slot].name:"exynos9810-clkout-unmapped"));
  u32 before=readl(out->gates[i].reg);
  clk_gate_endisable(&out->gates[i].hw,1);assert(readl(out->gates[i].reg)==(before&~1U));
  clk_gate_endisable(&out->gates[i].hw,0);assert(readl(out->gates[i].reg)==(before|1U));
  for(unsigned index=0;index<64;index++) {
   before=readl(out->muxes[i].reg);assert(clk_mux_set_parent(&out->muxes[i].hw,index)==0);
   assert(readl(out->muxes[i].reg)==((before&~(63U<<8))|(index<<8)));
  }
 }
 mmio[0xa00/4]=0xdeadbeef;mmio[0xa0c/4]=0x10203040;u32 unrelated=mmio[0xa04/4];
 int previous_writes=writes;assert(!exynos9810_clkout_suspend(&p.dev));assert(writes==previous_writes);
 mmio[0xa00/4]=0;mmio[0xa0c/4]=0;assert(!exynos9810_clkout_resume(&p.dev));
 assert(writes==previous_writes+2&&mmio[0xa00/4]==0xdeadbeef&&mmio[0xa0c/4]==0x10203040&&mmio[0xa04/4]==unrelated);
 exynos9810_clkout_remove(&p);assert(unregistered==2&&unreg_order[0]==1&&unreg_order[1]==0&&puts==2&&unmaps==1&&delprovider==1);
 /* Every partial probe path leaves no registered clock, map or parent reference. */
 for(int stage=0;stage<8;stage++) {
  reset();p.dev.data=NULL;
  if(stage<2)failalloc=stage+1;
  if(stage==2||stage==3)failparent=stage-2;
  if(stage==4)failmap=1;
  if(stage==5||stage==6)failreg=stage-5;
  if(stage==7)failprovider=1;
  assert(exynos9810_clkout_probe(&p)<0);
  assert(gets==puts&&maps==unmaps&&registered==unregistered&&writes==0&&!provider&&!delprovider&&!p.dev.data);
 }
 reset();node.is9810=false;assert(!exynos9810_clkout_device(&p.dev));p.dev.parent=NULL;assert(!exynos9810_clkout_device(&p.dev));
 reset();return 0;
}
'''


class ClkoutTests(unittest.TestCase):
    def setUp(self):
        if not all((FIXTURE/Path(e['path']).name).exists() for e in M['files']):self.skipTest('Set CLKOUT_FIXTURE to pristine source copies')

    def prepare(self,root):
        for e in M['files']:
            p=root/e['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((FIXTURE/p.name).read_bytes())

    def test_source_patches_and_existing_api_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.prepare(root);self.assertEqual(A.apply(root),2);self.assertEqual(A.apply(root),0)
            original=(FIXTURE/'clk-exynos-clkout.c').read_text();patched=(root/M['files'][0]['path']).read_text()
            stripped=re.sub(r'/\* BEGIN EXYNOS9810 DUAL CLKOUT.*?/\* END EXYNOS9810 DUAL CLKOUT \*/\n\n','',patched,flags=re.S)
            stripped=stripped.replace('\tif (exynos9810_clkout_device(&pdev->dev))\n\t\treturn exynos9810_clkout_probe(pdev);\n\n','',1)
            for fn in ['remove','suspend','resume']:
                argument='&pdev->dev' if fn=='remove' else 'dev'
                content='\t\texynos9810_clkout_remove(pdev);\n\t\treturn;\n' if fn=='remove' else '\t\treturn exynos9810_clkout_'+fn+'(dev);\n'
                stripped=stripped.replace('\n\n\tif (exynos9810_clkout_device('+argument+')) {\n'+content+'\t}\n','',1)
            self.assertEqual(stripped,original)
            for e in M['files']:
                self.assertEqual(A.checksum(root/e['path']),e['after_sha256'])
            dts=(root/M['files'][1]['path']).read_text()
            pmu=re.search(r'pmu_system_controller: system-controller@14060000\s*\{([^}]+)\}',dts).group(1)
            self.assertIn('#clock-cells = <1>;',pmu);self.assertIn('clocks = <&oscclk>, <&oscclk>;',pmu)
            self.assertIn('clock-names = "clkout0", "clkout1";',pmu)
            self.assertEqual(len(re.findall(r'clocks\s*=\s*<&pmu_system_controller',dts)),0)
            (root/M['files'][0]['path']).write_text('foreign drift')
            with self.assertRaises(RuntimeError):A.apply(root)

    def test_pinned_lineage_offsets_slots_polarity_and_consumers(self):
        lineage=Path(os.environ.get('LINEAGE_KERNEL_SOURCE','/Users/yongseok/Workspace/Codex/Galaxy-S9-Ubuntu/references/lineage-exynos9810'))
        if not (lineage/'.git').exists():self.skipTest('Set LINEAGE_KERNEL_SOURCE for independent pinned vendor-source check')
        def source(path):
            return subprocess.check_output(['git','-C',str(lineage),'show',M['lineage_commit']+':'+path],text=True)
        table=source('drivers/soc/samsung/cal-if/exynos9810/clkout_exynos9810.c')
        facts={k:int(v,0) for k,v in re.findall(r'#define\s+(CLKOUT[01]_\w+)\s+\((0x[0-9A-Fa-f]+|[0-9]+)\)',table)}
        for i,offset,slot in [(0,0xa00,1),(1,0xa0c,0)]:
            self.assertEqual(facts[f'CLKOUT{i}_OFFSET'],offset)
            self.assertEqual(facts[f'CLKOUT{i}_SEL_SHIFT'],8)
            self.assertEqual(facts[f'CLKOUT{i}_SEL_WIDTH'],6)
            self.assertEqual(facts[f'CLKOUT{i}_SEL_TCXO'],slot)
            self.assertEqual(facts[f'CLKOUT{i}_ENABLE_SHIFT'],0)
            self.assertEqual(facts[f'CLKOUT{i}_ENABLE_WIDTH'],1)
        ra=source('drivers/soc/samsung/cal-if/ra.c')
        flow=ra.split('int ra_enable_clkout(',1)[1].split('int ra_set_enable(',1)[0]
        self.assertIn('0x0 << clk->e_shift',flow)
        self.assertIn('0x1 << clk->e_shift',flow)
        clock=source('drivers/clk/samsung/clk-exynos9810.c')
        self.assertIn('VCLK(OSC_NFC, VCLK_CLKOUT1,',clock)
        self.assertIn('VCLK(OSC_AUD, VCLK_CLKOUT0,',clock)
        board=source('arch/arm64/boot/dts/exynos/exynos9810-star2lte_eur_open_26.dts')
        self.assertIn('clock-names = "oscclk_nfc";',board)
        self.assertIn('clocks = <0x1a 0x398>;',board)
        self.assertIn('clock-names = "xclkout";',board)
        self.assertIn('clocks = <0x1a 0x399>;',board)
        bindings=source('include/dt-bindings/clock/exynos9810.h')
        self.assertRegex(bindings,r'CLK_CLKOUT_BASE\s+\(920\)')
        self.assertRegex(bindings,r'OSC_NFC\s+\(CLK_CLKOUT_BASE \+ 0\)')
        self.assertRegex(bindings,r'OSC_AUD\s+\(CLK_CLKOUT_BASE \+ 1\)')

    def test_actual_provider_fake_mmio_and_unwind(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.prepare(root);A.apply(root)
            text=(root/M['files'][0]['path']).read_text()
            block=text.split('/* BEGIN EXYNOS9810 DUAL CLKOUT',1)[1].split('/* END EXYNOS9810 DUAL CLKOUT */',1)[0]
            block='/* BEGIN EXYNOS9810 DUAL CLKOUT'+block
            operations=[]
            for name,fn in [('clk-gate.c','clk_gate_endisable'),('clk-mux.c','clk_mux_set_parent')]:
                data=(FIXTURE/name).read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),M['test_references'][name])
                operations.append(function(data.decode(),fn))
            c=root/'check.c';exe=root/'check';c.write_text(STUB+'\n'+block+'\n'+'\n'.join(operations)+CASES)
            subprocess.run([os.environ.get('CC','cc'),'-std=gnu11','-fsanitize=address,undefined',str(c),'-o',str(exe)],capture_output=True,check=True)
            subprocess.run([str(exe)],capture_output=True,check=True,env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0'})


if __name__=='__main__':unittest.main()

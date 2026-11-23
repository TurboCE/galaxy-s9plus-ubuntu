// SPDX-License-Identifier: GPL-2.0-only
/* Read-only diagnosis against the exact qualified Panfrost source layout.
 * No GPU registers, runtime-PM references, jobs, clocks or resets are changed.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include "panfrost_device.h"
/* Private lock layout copied from the pinned panfrost_job.c, GPL-2.0:
 * Copyright 2019 Linaro, Ltd, Rob Herring <robh@kernel.org>
 * Copyright 2019 Collabora ltd.
 * The builder refuses changed source-layout hashes for this optional module.
 */
struct panfrost_queue_state {
 struct drm_gpu_scheduler sched;
 u64 fence_context;
 u64 emit_seqno;
};
struct panfrost_job_slot {
 struct panfrost_queue_state queue[NUM_JOB_SLOTS];
 spinlock_t job_lock;
 int irq;
};
static bool enable_g965n;
module_param(enable_g965n,bool,0400);
static struct device *gpu;
static int snapshot(char *buf,const struct kernel_param *kp)
{
 struct panfrost_device *p;unsigned long flags;int busy,jobs=0,i,j;u64 seq=0;char owner[32]="none";
 if(!gpu)return -ENODEV;
 p=dev_get_drvdata(gpu);
 if(!p || !p->pfdevfreq.devfreq)return -ENODEV;
 spin_lock_irqsave(&p->pfdevfreq.lock,flags);
 busy=p->pfdevfreq.busy_count;
 spin_unlock_irqrestore(&p->pfdevfreq.lock,flags);
 spin_lock_irqsave(&p->js->job_lock,flags);
 for(i=0;i<NUM_JOB_SLOTS;i++)for(j=0;j<2;j++) {
  struct panfrost_job *job=p->jobs[i][j];
  if(job) {jobs++;if(job->done_fence)seq+=job->done_fence->seqno;
   strscpy(owner,job->submitter_comm,sizeof(owner));}
 }
 spin_unlock_irqrestore(&p->js->job_lock,flags);
 return scnprintf(buf,PAGE_SIZE,"busy_count=%d jobs=%d pm_usage=%d profile=%u reset_pending=%d seq=%llu owner=%s\n",
 busy,jobs,atomic_read(&gpu->power.usage_count),READ_ONCE(p->profile_mode),atomic_read(&p->reset.pending),seq,owner);
}
static const struct kernel_param_ops ops={.get=snapshot};
module_param_cb(snapshot,&ops,NULL,0400);
static int __init start(void)
{
 if(!enable_g965n || !of_machine_is_compatible("samsung,star2lte"))return -EPERM;
 gpu=bus_find_device_by_name(&platform_bus_type,NULL,"17500000.gpu");
 return gpu?0:-ENODEV;
}
static void __exit stop(void){put_device(gpu);}
module_init(start);module_exit(stop);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Read-only SM-G965N Panfrost idle counters for exact native ABI");

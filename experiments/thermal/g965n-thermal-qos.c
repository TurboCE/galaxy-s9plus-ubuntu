// SPDX-License-Identifier: GPL-2.0-only
/* Battery-temperature cooling requests through standard CPU/devfreq QoS.
 * Does not program rails, raw clocks, charger bits or existing user requests.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/cpufreq.h>
#include <linux/pm_qos.h>
#include <linux/platform_device.h>
#include <linux/mutex.h>
static bool enable_g965n;
module_param(enable_g965n, bool, 0400);
static unsigned int level = 1;
static bool ready;
static DEFINE_MUTEX(lock);
static struct cpufreq_policy *policies[2];
static struct freq_qos_request caps[2];
static struct dev_pm_qos_request gpu_cap;
static struct device *gpu;
static int apply(unsigned int next)
{
 int i, ret;
 static const int limited[] = {650000, 1066000};
 /* Always tighten first; failures never release the other requests. */
 for (i=0;i<2;i++) {
  ret=freq_qos_update_request(&caps[i], next ? limited[i] : FREQ_QOS_MAX_DEFAULT_VALUE);
  if (ret<0) return ret;
 }
 ret=dev_pm_qos_update_request(&gpu_cap, next ? 260000 : PM_QOS_MAX_FREQUENCY_DEFAULT_VALUE);
 if (ret<0) return ret;
 level=next;
 return 0;
}
static int set_level(const char *value, const struct kernel_param *kp)
{
 unsigned int next;int ret=kstrtouint(value,0,&next);
 if (ret || next>1) return -EINVAL;
 mutex_lock(&lock);
 if (ready) {
  ret=apply(next);
  if (ret) apply(1); /* Best effort retain conservative requests on error. */
 } else level=next;
 mutex_unlock(&lock);
 return ret;
}
static const struct kernel_param_ops ops={.set=set_level,.get=param_get_uint};
module_param_cb(level,&ops,&level,0600);
static int __init init_qos(void)
{
 int i,ret;static const unsigned int cpus[]={0,4};
 if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte")) return -EPERM;
 gpu=bus_find_device_by_name(&platform_bus_type,NULL,"17500000.gpu");
 if (!gpu) return -ENODEV;
 for (i=0;i<2;i++) {
  policies[i]=cpufreq_cpu_get(cpus[i]);
  if (!policies[i]) {ret=-ENODEV;goto unwind;}
  ret=freq_qos_add_request(&policies[i]->constraints,&caps[i],FREQ_QOS_MAX,
                          level ? (i ? 1066000 : 650000) : FREQ_QOS_MAX_DEFAULT_VALUE);
  if (ret<0) {cpufreq_cpu_put(policies[i]);policies[i]=NULL;goto unwind;}
 }
 ret=dev_pm_qos_add_request(gpu,&gpu_cap,DEV_PM_QOS_MAX_FREQUENCY,
                            level ? 260000 : PM_QOS_MAX_FREQUENCY_DEFAULT_VALUE);
 if (ret<0) goto unwind;
 ready=true;return 0;
unwind:
 while (--i>=0) {freq_qos_remove_request(&caps[i]);cpufreq_cpu_put(policies[i]);}
 put_device(gpu);return ret;
}
static void __exit exit_qos(void)
{
 int i;mutex_lock(&lock);ready=false;
 dev_pm_qos_remove_request(&gpu_cap);
 for(i=1;i>=0;i--) {freq_qos_remove_request(&caps[i]);cpufreq_cpu_put(policies[i]);}
 put_device(gpu);mutex_unlock(&lock);
}
module_init(init_qos);module_exit(exit_qos);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SM-G965N calibrated battery cooling QoS requests");

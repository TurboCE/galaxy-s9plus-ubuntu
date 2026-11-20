// SPDX-License-Identifier: GPL-2.0-only
/* Bounded-QA helper: add only a lower MAX constraint, never raw clock writes. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/cpufreq.h>
#include <linux/pm_qos.h>
static bool enable_g965n;
module_param(enable_g965n, bool, 0400);
static struct cpufreq_policy *policy;
static struct freq_qos_request cap;
static int __init cap_init(void)
{
 int ret;
 if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte"))
  return -EPERM;
 policy = cpufreq_cpu_get(4);
 if (!policy)
  return -ENODEV;
 if (policy->cpuinfo.min_freq > 1794000 || policy->cpuinfo.max_freq < 1794000) {
  cpufreq_cpu_put(policy);
  return -EINVAL;
 }
 ret = freq_qos_add_request(&policy->constraints, &cap, FREQ_QOS_MAX, 1794000);
 if (ret < 0) {
  cpufreq_cpu_put(policy);
  return ret;
 }
 return 0;
}
static void __exit cap_exit(void)
{
 freq_qos_remove_request(&cap);
 cpufreq_cpu_put(policy);
}
module_init(cap_init);
module_exit(cap_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SM-G965N opt-in lower-MAX QoS qualification helper");

// SPDX-License-Identifier: GPL-2.0-only
/* Board-scoped input boost through standard CPU frequency QoS, not raw clocks.
 * No key codes/coordinates are recorded. Idle has no periodic work or floor.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/input.h>
#include <linux/cpufreq.h>
#include <linux/pm_qos.h>
#include <linux/workqueue.h>
#include <linux/mutex.h>
#include <linux/jiffies.h>

static bool enable_g965n;
module_param(enable_g965n, bool, 0400);
static unsigned int hold_ms = 500;
module_param(hold_ms, uint, 0400);
static struct cpufreq_policy *policies[2];
static struct freq_qos_request floors[2];
static unsigned int ceiling[2];
static DEFINE_MUTEX(boost_lock);
static unsigned long last_input;
static bool active, stopping;
static struct work_struct apply_work;
static struct delayed_work release_work;

static void release_floors(void)
{
 int i, ret;
 for (i = 0; i < 2; i++) {
  ret = freq_qos_update_request(&floors[i], FREQ_QOS_MIN_DEFAULT_VALUE);
  if (ret < 0)
   pr_err_ratelimited("g965n-input-boost: release failed: %d\n", ret);
 }
 active = false;
}

static void boost_apply(struct work_struct *work)
{
 int i, ret;
 mutex_lock(&boost_lock);
 if (READ_ONCE(stopping) || active ||
     time_after_eq(jiffies, READ_ONCE(last_input) + msecs_to_jiffies(hold_ms)))
  goto out;
 for (i = 0; i < 2; i++) {
  ret = freq_qos_update_request(&floors[i], ceiling[i]);
  if (ret < 0) {
   pr_err_ratelimited("g965n-input-boost: request failed: %d\n", ret);
   release_floors();
   goto out;
  }
 }
 active = true;
out:
 mutex_unlock(&boost_lock);
}

static void boost_release(struct work_struct *work)
{
 unsigned long deadline;
 mutex_lock(&boost_lock);
 deadline = READ_ONCE(last_input) + msecs_to_jiffies(hold_ms);
 if (!READ_ONCE(stopping) && time_before(jiffies, deadline))
  mod_delayed_work(system_wq, &release_work, deadline - jiffies);
 else
  release_floors();
 mutex_unlock(&boost_lock);
}

static bool boost_match(struct input_handler *handler, struct input_dev *dev)
{
 return (test_bit(EV_ABS, dev->evbit) &&
         test_bit(ABS_MT_POSITION_X, dev->absbit) &&
         test_bit(ABS_MT_POSITION_Y, dev->absbit)) ||
        (test_bit(EV_KEY, dev->evbit) && test_bit(KEY_A, dev->keybit) &&
         test_bit(KEY_LEFTMETA, dev->keybit));
}

static void boost_event(struct input_handle *handle, unsigned int type,
                        unsigned int code, int value)
{
 if (READ_ONCE(stopping))
  return;
 if (!((type == EV_KEY && value == 1) ||
       (type == EV_ABS && (code == ABS_MT_POSITION_X || code == ABS_MT_POSITION_Y))))
  return;
 WRITE_ONCE(last_input, jiffies);
 schedule_work(&apply_work);
 mod_delayed_work(system_wq, &release_work, msecs_to_jiffies(hold_ms));
}

static int boost_connect(struct input_handler *handler, struct input_dev *dev,
                         const struct input_device_id *id)
{
 struct input_handle *handle;
 int ret;
 handle = kzalloc(sizeof(*handle), GFP_KERNEL);
 if (!handle)
  return -ENOMEM;
 handle->dev = dev;
 handle->handler = handler;
 handle->name = "g965n-interactive-boost";
 ret = input_register_handle(handle);
 if (ret)
  goto free;
 ret = input_open_device(handle);
 if (ret)
  goto unregister;
 return 0;
unregister:
 input_unregister_handle(handle);
free:
 kfree(handle);
 return ret;
}

static void boost_disconnect(struct input_handle *handle)
{
 input_close_device(handle);
 input_unregister_handle(handle);
 kfree(handle);
}

static const struct input_device_id boost_ids[] = {
 { .flags = INPUT_DEVICE_ID_MATCH_EVBIT, .evbit = { BIT_MASK(EV_KEY) } },
 { .flags = INPUT_DEVICE_ID_MATCH_EVBIT, .evbit = { BIT_MASK(EV_ABS) } },
 { },
};
static struct input_handler boost_handler = {
 .event = boost_event,
 .match = boost_match,
 .connect = boost_connect,
 .disconnect = boost_disconnect,
 .name = "g965n-interactive-boost",
 .id_table = boost_ids,
};

static int __init boost_init(void)
{
 static const unsigned int cpus[] = { 0, 4 };
 static const unsigned int qualified_max[] = { 1499333, 2327000 };
 int i, j, ret;
 if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte") ||
     hold_ms < 100 || hold_ms > 1000)
  return -EPERM;
 INIT_WORK(&apply_work, boost_apply);
 INIT_DELAYED_WORK(&release_work, boost_release);
 for (i = 0; i < 2; i++) {
  policies[i] = cpufreq_cpu_get(cpus[i]);
  if (!policies[i]) {
   ret = -ENODEV;
   goto unwind;
  }
  /* A transient boot/thermal cap must not become a permanent target.
   * Standard policy MAX constraints still clamp the effective floor. */
  ceiling[i] = min(policies[i]->cpuinfo.max_freq, qualified_max[i]);
  if (!ceiling[i] || ceiling[i] < policies[i]->cpuinfo.min_freq ||
      (i && policies[i] == policies[0])) {
   ret = -EINVAL;
   cpufreq_cpu_put(policies[i]);
   policies[i] = NULL;
   goto unwind;
  }
  ret = freq_qos_add_request(&policies[i]->constraints, &floors[i],
                            FREQ_QOS_MIN, FREQ_QOS_MIN_DEFAULT_VALUE);
  if (ret < 0) {
   cpufreq_cpu_put(policies[i]);
   policies[i] = NULL;
   goto unwind;
  }
 }
 ret = input_register_handler(&boost_handler);
 if (!ret)
  return 0;
 WRITE_ONCE(stopping, true);
 cancel_work_sync(&apply_work);
 cancel_delayed_work_sync(&release_work);
 i = 2;
unwind:
 for (j = i - 1; j >= 0; j--) {
  freq_qos_remove_request(&floors[j]);
  cpufreq_cpu_put(policies[j]);
 }
 return ret;
}

static void __exit boost_exit(void)
{
 int i;
 WRITE_ONCE(stopping, true);
 input_unregister_handler(&boost_handler);
 cancel_work_sync(&apply_work);
 cancel_delayed_work_sync(&release_work);
 mutex_lock(&boost_lock);
 release_floors();
 mutex_unlock(&boost_lock);
 for (i = 1; i >= 0; i--) {
  freq_qos_remove_request(&floors[i]);
  cpufreq_cpu_put(policies[i]);
 }
}
module_init(boost_init);
module_exit(boost_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SM-G965N bounded event-driven CPU frequency QoS hint");

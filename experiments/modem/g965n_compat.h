/* SPDX-License-Identifier: GPL-2.0-only */
/* Legacy LineageOS modem API adapters to Linux 7.1. No hardware IO here. */
#pragma once
#define CONFIG_SOC_EXYNOS9810 1
#define CONFIG_MCU_IPC 1
#define CONFIG_SHM_IPC 1
#define CONFIG_SEC_SIPC_MODEM_IF 1
#define CONFIG_SEC_MODEM_SS310AP 1
#define CONFIG_UMTS_MODEM_SS310AP 1
#define CONFIG_LINK_DEVICE_SHMEM 1
#define CONFIG_LINK_DEVICE_NAPI 1
#define CONFIG_CP_SECURE_BOOT 1
#define CONFIG_CP_PMUCAL 1
#define CONFIG_MODEM_IF_QOS 1
#define CONFIG_MODEM_IF_NET_GRO 1
#define CONFIG_CP_RAM_LOGGING 1

#include <linux/types.h>
#include <linux/vmalloc.h>
#include <linux/kernel.h>
#include <linux/string.h>
#include <linux/time64.h>
#include <linux/timekeeping.h>
#include <linux/sched/clock.h>
#include <linux/timer.h>
#include <linux/hrtimer.h>
#include <linux/etherdevice.h>
#include <linux/proc_fs.h>
#include <linux/pm_wakeup.h>
#include <linux/arm-smccc.h>
#include <linux/pm_qos.h>
#include <linux/netdevice.h>

/* Name-only adaptations of public kernel APIs. */
#define timespec timespec64
#define getnstimeofday ktime_get_real_ts64
#define timespec_sub timespec64_sub
#define timespec_to_ns timespec64_to_ns
#define time_to_tm time64_to_tm
#define cpu_clock(cpu) local_clock()
#define strlcpy strscpy
#define PDE_DATA pde_data
#define random_ether_addr eth_random_addr
#define del_timer timer_delete
#define del_timer_sync timer_delete_sync

struct wake_lock { struct wakeup_source *source; };
#define WAKE_LOCK_SUSPEND 0
static inline void wake_lock_init(struct wake_lock *lock, int kind, const char *name)
{ lock->source = wakeup_source_register(NULL, name); }
static inline void wake_lock_destroy(struct wake_lock *lock)
{ wakeup_source_unregister(lock->source); lock->source = NULL; }
static inline void wake_lock(struct wake_lock *lock)
{ if (lock->source) __pm_stay_awake(lock->source); }
static inline void wake_unlock(struct wake_lock *lock)
{ if (lock->source) __pm_relax(lock->source); }
static inline void wake_lock_timeout(struct wake_lock *lock, long delay)
{ if (lock->source) __pm_wakeup_event(lock->source, jiffies_to_msecs(delay)); }
static inline int wake_lock_active(struct wake_lock *lock)
{ return lock->source && lock->source->active; }

/* Vendor bus QoS classes have no equivalent policy in this port yet.
 * Keep this gap visible; this module is NOT hardware qualified. */
#define PM_QOS_CLUSTER0_FREQ_MIN 1
#define PM_QOS_CLUSTER1_FREQ_MIN 2
#define PM_QOS_BUS_THROUGHPUT 3
#define PM_QOS_DEVICE_THROUGHPUT 4
#define pm_qos_add_request(...) do { pr_warn_once("g965n-mif: vendor bus QoS is not implemented\n"); } while (0)
#define pm_qos_update_request(...) do { } while (0)
#define pm_qos_remove_request(...) do { } while (0)
#define exynos_ss_set_enable(...) do { } while (0)
#define acpm_stop_log() do { } while (0)
static inline int gpio_export(unsigned int gpio, bool change) { return 0; }
static inline int gpio_export_link(struct device *dev, const char *name, unsigned int gpio) { return 0; }
static inline int exynos_smc(unsigned long id, unsigned long a, unsigned long b, unsigned long c)
{
    struct arm_smccc_res reply;
    arm_smccc_smc(id, a, b, c, 0, 0, 0, 0, &reply);
    return (int)reply.a0;
}
int cal_cp_init(void);
int cal_cp_status(void);
int cal_cp_reset_assert(void);
int cal_cp_reset_release(void);
void cal_cp_active_clear(void);
void cal_cp_reset_req_clear(void);
void cal_cp_enable_dump_pc_no_pg(void);
void cal_cp_disable_dump_pc_no_pg(void);
#define SMC_ID 0x82000700
extern struct napi_struct *zrn_napi;
#define napi_get_current() zrn_napi
#define napi_gro_flush(...) do { } while (0)
#define GRO_DROP ((gro_result_t)-1)
static inline enum hrtimer_restart g965n_empty_timer(struct hrtimer *timer) { return HRTIMER_NORESTART; }
#define hrtimer_init(timer, clock, mode) hrtimer_setup(timer, g965n_empty_timer, clock, mode)
#define free_memsize_reserved(...) do { } while (0)
dma_addr_t shm_zmb_dma_addr(void *address);

# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'experiments/sensors/bbd.c'


class PatchWatchdogTests(unittest.TestCase):
    def test_actual_watchdog_cancels_queued_work_before_rearm_and_teardown(self):
        source = SOURCE.read_text()
        start = source.index('static void bbd_lk_work(')
        end = source.index('\n#endif', start)
        timeout_start = source.index('static ssize_t store_sysfs_lk_timeout(')
        timeout_end = source.index('static ssize_t show_sysfs_lk_timeout(', timeout_start)
        with tempfile.TemporaryDirectory() as directory:
            test = Path(directory) / 'watchdog.c'
            binary = Path(directory) / 'watchdog'
            test.write_text(STUBS + source[start:end] + source[timeout_start:timeout_end] + CASES)
            subprocess.run([os.getenv('CC', 'cc'), '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-parameter', str(test), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


STUBS = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <string.h>
#include <sys/types.h>

#define HZ 250UL
#define MAX_JIFFY_OFFSET (LONG_MAX / 2)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x, value) ((x) = (value))
#define min_t(t, a, b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define pr_info(...)
struct device;
struct device_attribute;
struct work_struct { void (*callback)(struct work_struct *); };
struct delayed_work { struct work_struct work; bool pending; };
struct workqueue_struct { int unused; };
static struct workqueue_struct queue;
static bool bbd_lk_watchdog_lock, fail_allocation;
static unsigned int initializations, cancels, schedules, resets, destroyed;
static unsigned long delay;
static struct {
    struct {
        bool enabled;
        long timeout_sec;
        int lock;
        struct delayed_work watchdog;
        struct workqueue_struct *workq;
    } lk;
} bbd;

static void mutex_lock(bool *lock) { assert(!*lock); *lock=true; }
static void mutex_unlock(bool *lock) { assert(*lock); *lock=false; }
static void spin_lock_init(int *lock) { *lock=0; }
static void INIT_DELAYED_WORK(struct delayed_work *work, void (*cb)(struct work_struct *))
{ assert(bbd_lk_watchdog_lock); work->work.callback=cb; initializations++; }
static struct workqueue_struct *create_singlethread_workqueue(const char *name)
{ assert(bbd_lk_watchdog_lock && name); return fail_allocation?NULL:&queue; }
static void cancel_delayed_work_sync(struct delayed_work *work)
{ assert(bbd_lk_watchdog_lock && work->work.callback); work->pending=false; cancels++; }
static void queue_delayed_work(struct workqueue_struct *wq,struct delayed_work *work,unsigned long ticks)
{ assert(wq==&queue && bbd_lk_watchdog_lock && !work->pending); delay=ticks; work->pending=true; schedules++; }
static void destroy_workqueue(struct workqueue_struct *wq)
{ assert(wq==&queue && bbd_lk_watchdog_lock && !bbd.lk.watchdog.pending); destroyed++; }
static void bbd_mcu_reset(bool no_response)
{ assert(!no_response && !bbd_lk_watchdog_lock); resets++; }
static int kstrtol(const char *s, int base, long *v)
{
    assert(base==0);
    if (!strcmp(s,"invalid")) return -EINVAL;
    *v=!strcmp(s,"overflow-delay")?LONG_MAX:-1;
    return 0;
}
'''


CASES = r'''
int main(void)
{
    struct delayed_work *work=&bbd.lk.watchdog;
    bbd_init_lk();
    assert(initializations==1 && !work->pending);
    bbd_enable_lk();
    assert(work->pending && delay==HZ*10 && cancels==1 && schedules==1);
    bbd_enable_lk();
    assert(work->pending && initializations==1 && cancels==2 && schedules==2);
    bbd_disable_lk();
    assert(!work->pending && cancels==3 && resets==0);
    assert(store_sysfs_lk_timeout(NULL,NULL,"invalid",7)==-EINVAL && bbd.lk.timeout_sec==10);
    assert(store_sysfs_lk_timeout(NULL,NULL,"negative",8)==8 && bbd.lk.timeout_sec==10);
    assert(store_sysfs_lk_timeout(NULL,NULL,"overflow-delay",14)==14);
    bbd_enable_lk();
    assert(delay==(MAX_JIFFY_OFFSET/HZ)*HZ);
    work->pending=false;
    work->work.callback(&work->work);
    assert(resets==1);
    bbd_enable_lk();
    bbd_exit_lk();
    assert(!work->pending && destroyed==1 && !bbd.lk.workq);
    assert(initializations==1 && schedules==4 && cancels==6);

    fail_allocation=true;
    bbd_init_lk();
    bbd_enable_lk();
    bbd_disable_lk();
    bbd_exit_lk();
    assert(!work->pending && schedules==4 && cancels==6 && destroyed==1);
    return 0;
}
'''

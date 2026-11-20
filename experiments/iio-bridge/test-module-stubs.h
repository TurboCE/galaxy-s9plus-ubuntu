/* SPDX-License-Identifier: GPL-2.0-only */
/* Host-only stubs; the tested implementation is the actual module source. */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <fcntl.h>
#include "bridge-core.h"
#define __user
#define __init
#define __exit
#define module_param(...)
#define module_param_array_named(...)
#define MODULE_PARM_DESC(...)
#define MODULE_LICENSE(...)
#define MODULE_DESCRIPTION(...)
#define module_init(...)
#define module_exit(...)
#undef static_assert
#define static_assert(x) _Static_assert(x,#x)
#define THIS_MODULE ((void *)1)
#define BIT(n) (1U<<(n))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define CAP_SYS_ADMIN 1
#define IIO_ACCEL 1
#define IIO_LIGHT 2
#define IIO_PRESSURE 3
#define IIO_PROXIMITY 4
#define IIO_ANGL_VEL 5
#define IIO_TEMP 6
#define IIO_MOD_X 1
#define IIO_MOD_Y 2
#define IIO_MOD_Z 3
#define IIO_CHAN_INFO_RAW 0
#define IIO_CHAN_INFO_PROCESSED 1
#define IIO_CHAN_INFO_SCALE 2
#define IIO_VAL_INT 1
#define IIO_VAL_INT_PLUS_NANO 3
#define IIO_VAL_FRACTIONAL 10
#define INDIO_DIRECT_MODE 1
#define IIO_SHARED_BY_TYPE 1
#define IIO_SEPARATE 0
#define MISC_DYNAMIC_MINOR 255
struct mutex {bool locked;};
#define DEFINE_MUTEX(name) struct mutex name
static void mutex_lock(struct mutex *m){assert(!m->locked);m->locked=true;}
static void mutex_unlock(struct mutex *m){assert(m->locked);m->locked=false;}
static bool cap=true,board=true,chip=true;
static u64 clock_ns=10000000000ULL;
static bool capable(int c){assert(c==CAP_SYS_ADMIN);return cap;}
static bool of_machine_is_compatible(const char *s){return !strcmp(s,"samsung,star2lte")?board:!strcmp(s,"samsung,exynos9810")?chip:false;}
static u64 ktime_get_boottime_ns(void){return clock_ns;}
typedef long long loff_t;
#define FMODE_LSEEK 1U
#define FMODE_PREAD 2U
#define FMODE_PWRITE 4U
#define FMODE_ATOMIC_POS 8U
#define FMODE_STREAM 16U
struct inode {int unused;};struct file {int f_flags;unsigned int f_mode;};
static unsigned int stream_opens;
/* Exact pinned Linux7.1 fs/open.c semantics, without a position or seek API. */
static int stream_open(struct inode *inode,struct file *file)
{
 file->f_mode &= ~(FMODE_LSEEK|FMODE_PREAD|FMODE_PWRITE|FMODE_ATOMIC_POS);
 file->f_mode |= FMODE_STREAM;stream_opens++;return 0;
}
static int copy_fail,copy_count;
static unsigned long copy_from_user(void *d,const void *s,size_t n){copy_count++;if(copy_fail)return n;memcpy(d,s,n);return 0;}
struct device {int unused;};
struct iio_mount_matrix {const char *rotation[9];};
struct iio_dev;
struct iio_chan_spec;
struct iio_chan_spec_ext_info {const char *name;int shared;ssize_t (*read)(struct iio_dev *,uintptr_t,const struct iio_chan_spec *,char *);};
#define IIO_MOUNT_MATRIX(...) {.name="mount_matrix"}
#define sysfs_emit(buf, text) ((ssize_t)strlen(strcpy(buf,text)))
struct iio_chan_spec {int type,modified,channel2,indexed,channel;unsigned int info_mask_separate,info_mask_shared_by_type;const struct iio_chan_spec_ext_info *ext_info;const char *datasheet_name;};
struct iio_info {int (*read_raw)(struct iio_dev *,const struct iio_chan_spec *,int *,int *,long);};
struct iio_dev {const char *name;const struct iio_info *info;int modes;const struct iio_chan_spec *channels;unsigned int num_channels;};
struct file_operations {void *owner;int (*open)(struct inode *,struct file *);ssize_t (*write)(struct file *,const char *,size_t,loff_t *);int (*release)(struct inode *,struct file *);void *llseek;};
struct miscdevice {int minor;const char *name;const struct file_operations *fops;int mode;struct device *this_device;};
static int allocation_fail,registration_fail,allocations,registrations,unregistrations,frees,misc_registered;
static struct device parent;
static struct iio_dev *iio_device_alloc(struct device *p,int size){assert(p==&parent&&!size);if(allocation_fail)return NULL;allocations++;return calloc(1,sizeof(struct iio_dev));}
static void iio_device_free(struct iio_dev *p){frees++;free(p);}
static int iio_device_register(struct iio_dev *p);
static void iio_device_unregister(struct iio_dev *p);
static int misc_register(struct miscdevice *m){assert(m->mode==0600);misc_registered++;m->this_device=&parent;return 0;}
static void misc_deregister(struct miscdevice *m){misc_registered--;}

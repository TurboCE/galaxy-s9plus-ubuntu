// SPDX-License-Identifier: GPL-2.0-only
/* Real SSP samples supplied by the separately verified root broker. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/fs.h>
#include <linux/miscdevice.h>
#include <linux/capability.h>
#include <linux/uaccess.h>
#include <linux/mutex.h>
#include <linux/ktime.h>
#include <linux/iio/iio.h>
#include "bridge-core.h"

static bool enable_g965n;
module_param(enable_g965n, bool, 0444);
static bool enable_accel;
module_param(enable_accel, bool, 0444);
MODULE_PARM_DESC(enable_accel, "Opt-in acceleration only after actual mounting evidence; default ALS-only");
static int accel_matrix[9], accel_matrix_count;
module_param_array_named(accel_mount_matrix, accel_matrix, int, &accel_matrix_count, 0444);
MODULE_PARM_DESC(accel_mount_matrix, "Required explicit9-entry signed permutation, sensor to display axes");
static DEFINE_MUTEX(lifecycle_lock);
static DEFINE_MUTEX(sample_lock);
static struct bridge_cache cache;
static struct iio_dev *accel_dev, *light_dev;
static bool writer_open;
static struct iio_mount_matrix mount;
static struct miscdevice bridge_misc;

static const struct iio_mount_matrix *get_mount(const struct iio_dev *dev,
                                               const struct iio_chan_spec *chan)
{ return &mount; }
static const struct iio_chan_spec_ext_info accel_ext[] = {
 IIO_MOUNT_MATRIX(IIO_SHARED_BY_TYPE, get_mount), { }
};
#define ACCEL_CHANNEL(axis) { .type=IIO_ACCEL, .modified=1, .channel2=IIO_MOD_##axis, \
 .info_mask_separate=BIT(IIO_CHAN_INFO_RAW), \
 .info_mask_shared_by_type=BIT(IIO_CHAN_INFO_SCALE), .ext_info=accel_ext }
static const struct iio_chan_spec accel_channels[] = {
 ACCEL_CHANNEL(X), ACCEL_CHANNEL(Y), ACCEL_CHANNEL(Z)
};
static const struct iio_chan_spec light_channels[] = {
 { .type=IIO_LIGHT, .info_mask_separate=BIT(IIO_CHAN_INFO_PROCESSED) }
};
static int read_sample(struct iio_dev *dev,const struct iio_chan_spec *chan,
                       int *val,int *val2,long mask)
{
 u32 type=chan->type==IIO_ACCEL?G965N_IIO_ACCEL:G965N_IIO_LIGHT;
 unsigned int axis=chan->type==IIO_ACCEL?chan->channel2-IIO_MOD_X:0;
 s32 sample;int ret;
 mutex_lock(&sample_lock);
 if (mask==IIO_CHAN_INFO_SCALE && type==G965N_IIO_ACCEL) {
  /* Registration requires a verified range8 actual frame. */
  ret=cache.connected && cache.accel.valid?IIO_VAL_INT_PLUS_NANO:-ENODATA;
  if (ret>=0) {*val=0;*val2=2394202;}
 } else if ((mask==IIO_CHAN_INFO_RAW && type==G965N_IIO_ACCEL) ||
            (mask==IIO_CHAN_INFO_PROCESSED && type==G965N_IIO_LIGHT)) {
  ret=bridge_read(&cache,type,axis,ktime_get_boottime_ns(),&sample);
  if (!ret) {*val=sample;ret=IIO_VAL_INT;}
 } else ret=-EINVAL;
 mutex_unlock(&sample_lock);
 return ret;
}
static const struct iio_info sample_info = { .read_raw=read_sample };
static int register_sensor(u32 type)
{
 struct iio_dev *dev;struct iio_dev **target=type==G965N_IIO_ACCEL?&accel_dev:&light_dev;
 int ret;
 if (type==G965N_IIO_ACCEL && !enable_accel) return -EACCES;
 if (*target) return 0;
 dev=iio_device_alloc(bridge_misc.this_device,0);
 if (!dev) return -ENOMEM;
 dev->name=type==G965N_IIO_ACCEL?"g965n-ssp-accel":"g965n-ssp-light";
 dev->info=&sample_info;dev->modes=INDIO_DIRECT_MODE;
 dev->channels=type==G965N_IIO_ACCEL?accel_channels:light_channels;
 dev->num_channels=type==G965N_IIO_ACCEL?ARRAY_SIZE(accel_channels):ARRAY_SIZE(light_channels);
 ret=iio_device_register(dev);
 if (ret) {iio_device_free(dev);return ret;}
 *target=dev;return 0;
}
static int bridge_open(struct inode *inode,struct file *file)
{
 int ret=0;
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 if ((file->f_flags&O_ACCMODE)!=O_WRONLY) return -EACCES;
 mutex_lock(&lifecycle_lock);
 if (writer_open) ret=-EBUSY;
 else {
  writer_open=true;
  mutex_lock(&sample_lock);memset(&cache,0,sizeof(cache));cache.connected=true;mutex_unlock(&sample_lock);
 }
 mutex_unlock(&lifecycle_lock);
 return ret;
}
static ssize_t bridge_write(struct file *file,const char __user *user,size_t bytes,loff_t *position)
{
 struct g965n_iio_frame packet;struct bridge_decoded decoded;
 struct bridge_cache old;int ret;
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 if (bytes!=sizeof(packet)) return -EMSGSIZE;
 if (copy_from_user(&packet,user,sizeof(packet))) return -EFAULT;
 mutex_lock(&lifecycle_lock);
 if (!enable_accel && bridge_le32(packet.type)==G965N_IIO_ACCEL) {ret=-EACCES;goto out;}
 ret=bridge_decode(&packet,bytes,cache.seq,&decoded);
 if (ret) goto out;
 mutex_lock(&sample_lock);old=cache;bridge_update(&cache,&decoded,ktime_get_boottime_ns());mutex_unlock(&sample_lock);
 if (decoded.type!=G965N_IIO_HEARTBEAT) {
  ret=register_sensor(decoded.type);
  if (ret) {mutex_lock(&sample_lock);cache=old;mutex_unlock(&sample_lock);goto out;}
 }
 ret=sizeof(packet);
out:
 mutex_unlock(&lifecycle_lock);return ret;
}
static int bridge_close(struct inode *inode,struct file *file)
{
 mutex_lock(&lifecycle_lock);
 mutex_lock(&sample_lock);cache.connected=false;cache.accel.valid=false;cache.light.valid=false;mutex_unlock(&sample_lock);
 /* Never hold sample_lock across kernfs/IIO removal: active read_raw may use it. */
 if (light_dev) {iio_device_unregister(light_dev);iio_device_free(light_dev);light_dev=NULL;}
 if (accel_dev) {iio_device_unregister(accel_dev);iio_device_free(accel_dev);accel_dev=NULL;}
 writer_open=false;
 mutex_unlock(&lifecycle_lock);return 0;
}
static const struct file_operations bridge_fops = {
 .owner=THIS_MODULE,.open=bridge_open,.write=bridge_write,.release=bridge_close,.llseek=no_llseek
};
static struct miscdevice bridge_misc = {
 .minor=MISC_DYNAMIC_MINOR,.name="g965n-iio-bridge",.fops=&bridge_fops,.mode=0600
};
static int __init bridge_init(void)
{
 unsigned int i;
 static_assert(sizeof(struct g965n_iio_frame)==G965N_IIO_FRAME_BYTES);
 if (!enable_g965n || !of_machine_is_compatible("samsung,star2lte") ||
     !of_machine_is_compatible("samsung,exynos9810")) return -ENODEV;
 if (enable_accel) {
  if (!bridge_matrix_valid(accel_matrix,accel_matrix_count)) return -EINVAL;
  for (i=0;i<9;i++) mount.rotation[i]=accel_matrix[i]<0?"-1":accel_matrix[i]?"1":"0";
 }
 return misc_register(&bridge_misc);
}
static void __exit bridge_exit(void)
{
 /* .owner pins the module while a writer fd exists; release has removed IIO. */
 misc_deregister(&bridge_misc);
}
module_init(bridge_init);module_exit(bridge_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Opt-in G965N real SSP broker to standard IIO bridge");

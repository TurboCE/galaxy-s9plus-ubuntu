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
#include <linux/sysfs.h>
#include <linux/iio/iio.h>
#ifdef CONFIG_IIO
#include <linux/iio/driver.h>
#include <linux/iio/machine.h>
#include <linux/platform_device.h>
#endif
#ifdef CONFIG_IIO_TRIGGERED_BUFFER
#include <linux/iio/buffer.h>
#include <linux/iio/trigger.h>
#include <linux/iio/trigger_consumer.h>
#include <linux/iio/triggered_buffer.h>
#endif
#include "bridge-core.h"

static bool enable_g965n;
module_param(enable_g965n, bool, 0444);
static bool enable_accel;
module_param(enable_accel, bool, 0444);
MODULE_PARM_DESC(enable_accel, "Opt-in acceleration only after actual mounting evidence; default ALS-only");
static bool enable_pressure;
module_param(enable_pressure, bool, 0444);
MODULE_PARM_DESC(enable_pressure, "Opt-in LPS22H pressure on the qualified SSP profile");
static bool enable_proximity;
module_param(enable_proximity, bool, 0444);
MODULE_PARM_DESC(enable_proximity, "Opt-in TMD4906 proximity on the qualified SSP profile");
static bool enable_gyro;
module_param(enable_gyro, bool, 0444);
MODULE_PARM_DESC(enable_gyro, "Opt-in raw LSM6DSL gyro samples on the qualified SSP profile");
static bool enable_thermistor;
module_param(enable_thermistor, bool, 0444);
MODULE_PARM_DESC(enable_thermistor, "Opt-in read-only board thermistor values");
static int accel_matrix[9], accel_matrix_count;
module_param_array_named(accel_mount_matrix, accel_matrix, int, &accel_matrix_count, 0444);
MODULE_PARM_DESC(accel_mount_matrix, "Required explicit9-entry signed permutation, sensor to display axes");
static DEFINE_MUTEX(lifecycle_lock);
static DEFINE_MUTEX(sample_lock);
static struct bridge_cache cache;
static struct iio_dev *accel_dev, *light_dev, *pressure_dev, *proximity_dev, *gyro_dev;
static struct iio_dev *thermistor_dev;
static bool writer_open;
static struct iio_mount_matrix mount;
static struct miscdevice bridge_misc;

#ifdef CONFIG_IIO
static bool enable_hwmon;
module_param(enable_hwmon, bool, 0444);
MODULE_PARM_DESC(enable_hwmon, "Expose pressure-die and board temperatures to iio_hwmon");
static struct platform_device *barometer_hwmon, *board_hwmon;
static const struct iio_map barometer_map[] = {
 IIO_MAP("barometer_temp", "iio_hwmon.0", "barometer"),
 { }
};
static const struct iio_map board_map[] = {
 IIO_MAP("board_temp0", "iio_hwmon.1", "board0"),
 IIO_MAP("board_temp1", "iio_hwmon.1", "board1"),
 { }
};

static int register_hwmon(struct iio_dev *dev, u32 type)
{
 struct platform_device **target, *consumer;
 const struct iio_map *map;
 int id, ret;

 if (!enable_hwmon)
  return 0;
 if (type == G965N_IIO_PRESSURE) {
  id = 0;
  target = &barometer_hwmon;
  map = barometer_map;
 } else if (type == G965N_IIO_THERMISTOR) {
  id = 1;
  target = &board_hwmon;
  map = board_map;
 } else {
  return 0;
 }
 ret = iio_map_array_register(dev, map);
 if (ret)
  return ret;
 consumer = platform_device_register_simple("iio_hwmon", id, NULL, 0);
 if (IS_ERR(consumer)) {
  iio_map_array_unregister(dev);
  return PTR_ERR(consumer);
 }
 *target = consumer;
 return 0;
}

static void remove_hwmon(struct iio_dev *dev, struct platform_device **target)
{
 if (!*target)
  return;
 platform_device_unregister(*target);
 iio_map_array_unregister(dev);
 *target = NULL;
}
#endif

#ifdef CONFIG_IIO_TRIGGERED_BUFFER
static bool enable_heading;
module_param(enable_heading, bool, 0444);
MODULE_PARM_DESC(enable_heading, "Opt-in calibrated magnetic heading for IIO Sensor Proxy");
static struct iio_dev *heading_dev;
static struct iio_trigger *heading_trigger;
static u32 heading_sample;

static const struct iio_chan_spec heading_channel = {
 .type=IIO_ROT, .modified=1, .channel2=IIO_MOD_NORTH_MAGN_TILT_COMP,
 .info_mask_shared_by_type=BIT(IIO_CHAN_INFO_SCALE),
 .scan_index=0,
 .scan_type={.sign='u', .realbits=32, .storagebits=32, .endianness=IIO_CPU},
};

static int heading_scale(struct iio_dev *dev, const struct iio_chan_spec *chan,
                         int *val, int *val2, long mask)
{
 if (mask!=IIO_CHAN_INFO_SCALE) return -EINVAL;
 *val=0;
 *val2=1000;
 return IIO_VAL_INT_PLUS_MICRO;
}

static irqreturn_t heading_push(int irq, void *data)
{
 struct iio_poll_func *poll=data;
 u32 sample=READ_ONCE(heading_sample);

 iio_push_to_buffers(poll->indio_dev,&sample);
 iio_trigger_notify_done(poll->indio_dev->trig);
 return IRQ_HANDLED;
}

static int heading_validate_device(struct iio_trigger *trigger, struct iio_dev *dev)
{
 return iio_trigger_get_drvdata(trigger)==dev?0:-EINVAL;
}

static const struct iio_info heading_info = { .read_raw=heading_scale };
static const struct iio_trigger_ops heading_trigger_ops = {
 .validate_device=heading_validate_device,
};

/* Producer calls this under lifecycle_lock, from process context. */
static int publish_heading(u32 sample)
{
 struct device *parent=bridge_misc.this_device;
 struct iio_dev *dev;
 struct iio_trigger *trigger;
 int ret;

 if (!enable_heading) return -EACCES;
 if (!heading_dev) {
  dev=iio_device_alloc(parent,0);
  if (!dev) return -ENOMEM;
  trigger=iio_trigger_alloc(parent,"magn_3d-dev%d",iio_device_id(dev));
  if (!trigger) {ret=-ENOMEM;goto free_dev;}
  trigger->ops=&heading_trigger_ops;
  iio_trigger_set_drvdata(trigger,dev);
  dev->name="g965n-ssp-compass";
  dev->info=&heading_info;
  dev->channels=&heading_channel;
  dev->num_channels=1;
  ret=iio_triggered_buffer_setup(dev,NULL,heading_push,NULL);
  if (ret) goto free_trigger;
  /* Sensor Proxy discovers the associated trigger on device add. */
  ret=iio_trigger_register(trigger);
  if (ret) goto cleanup_buffer;
  ret=iio_device_register(dev);
  if (ret) goto unregister_trigger;
  heading_dev=dev;
  heading_trigger=trigger;
 }
 WRITE_ONCE(heading_sample,sample);
 iio_trigger_poll_nested(heading_trigger);
 return 0;

unregister_trigger:
 iio_trigger_unregister(trigger);
cleanup_buffer:
 iio_triggered_buffer_cleanup(dev);
free_trigger:
 iio_trigger_free(trigger);
free_dev:
 iio_device_free(dev);
 return ret;
}

static void remove_heading(void)
{
 if (!heading_dev) return;
 iio_device_unregister(heading_dev);
 iio_trigger_unregister(heading_trigger);
 iio_triggered_buffer_cleanup(heading_dev);
 iio_trigger_free(heading_trigger);
 iio_device_free(heading_dev);
 heading_dev=NULL;
 heading_trigger=NULL;
}
#else
static int publish_heading(u32 sample) { return -EOPNOTSUPP; }
static void remove_heading(void) { }
#endif

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
static const struct iio_chan_spec pressure_channels[] = {
 { .type=IIO_PRESSURE, .info_mask_separate=BIT(IIO_CHAN_INFO_RAW),
   .info_mask_shared_by_type=BIT(IIO_CHAN_INFO_SCALE) },
 { .type=IIO_TEMP, .datasheet_name="barometer_temp",
   .info_mask_separate=BIT(IIO_CHAN_INFO_PROCESSED) },
};
static ssize_t read_nearlevel(struct iio_dev *dev, uintptr_t private,
                             const struct iio_chan_spec *chan, char *buf)
{
 return sysfs_emit(buf,"1\n");
}
static const struct iio_chan_spec_ext_info proximity_ext[] = {
 { .name="nearlevel", .shared=IIO_SEPARATE, .read=read_nearlevel }, { }
};
static const struct iio_chan_spec proximity_channels[] = {
 { .type=IIO_PROXIMITY, .info_mask_separate=BIT(IIO_CHAN_INFO_RAW),
   .ext_info=proximity_ext },
};
#define GYRO_CHANNEL(axis) { .type=IIO_ANGL_VEL, .modified=1, .channel2=IIO_MOD_##axis, \
 .info_mask_separate=BIT(IIO_CHAN_INFO_RAW) }
static const struct iio_chan_spec gyro_channels[] = {
 GYRO_CHANNEL(X), GYRO_CHANNEL(Y), GYRO_CHANNEL(Z)
};
#define THERMISTOR_CHANNEL(number) { .type=IIO_TEMP, .indexed=1, .channel=(number), \
 .datasheet_name="board_temp" #number, \
 .info_mask_separate=BIT(IIO_CHAN_INFO_PROCESSED) }
static const struct iio_chan_spec thermistor_channels[] = {
 THERMISTOR_CHANNEL(0), THERMISTOR_CHANNEL(1)
};
static int read_sample(struct iio_dev *dev,const struct iio_chan_spec *chan,
                       int *val,int *val2,long mask)
{
 unsigned int axis=0;
 u32 type;
 s32 sample;int ret;
 bool processed=chan->type==IIO_LIGHT || chan->type==IIO_TEMP;
 switch (chan->type) {
 case IIO_ACCEL: type=G965N_IIO_ACCEL;axis=chan->channel2-IIO_MOD_X;break;
 case IIO_LIGHT: type=G965N_IIO_LIGHT;break;
 case IIO_PRESSURE: type=G965N_IIO_PRESSURE;break;
 case IIO_PROXIMITY: type=G965N_IIO_PROXIMITY;break;
 case IIO_ANGL_VEL: type=G965N_IIO_GYRO;axis=chan->channel2-IIO_MOD_X;break;
 case IIO_TEMP: type=G965N_IIO_THERMISTOR;axis=chan->channel;break;
 default: return -EINVAL;
 }
 mutex_lock(&sample_lock);
 if (mask==IIO_CHAN_INFO_SCALE && type==G965N_IIO_ACCEL) {
  /* Registration requires a verified range8 actual frame. */
  ret=cache.connected && cache.accel.valid?IIO_VAL_INT_PLUS_NANO:-ENODATA;
  if (ret>=0) {*val=0;*val2=2394202;}
 } else if (mask==IIO_CHAN_INFO_SCALE && type==G965N_IIO_PRESSURE) {
  /* The LPS22H yields 4096 counts/hPa. IIO reports kPa. */
  ret=cache.connected && cache.pressure.valid?IIO_VAL_FRACTIONAL:-ENODATA;
  if (ret>=0) {*val=1;*val2=40960;}
 } else if (mask==(processed?IIO_CHAN_INFO_PROCESSED:IIO_CHAN_INFO_RAW)) {
  ret=bridge_read(&cache,type,axis,ktime_get_boottime_ns(),&sample);
  /* Bracket the integer nearlevel and the proxy's hysteresis without
   * applying a second threshold to the hardware's raw ADC.
   */
  if (!ret && type==G965N_IIO_PROXIMITY) sample*=2;
  if (!ret) {*val=sample;ret=IIO_VAL_INT;}
 } else ret=-EINVAL;
 mutex_unlock(&sample_lock);
 return ret;
}
static const struct iio_info sample_info = { .read_raw=read_sample };
static int read_pressure(struct iio_dev *dev,const struct iio_chan_spec *chan,
                         int *val,int *val2,long mask)
{
 s32 sample;int ret;
 if (chan->type==IIO_PRESSURE) return read_sample(dev,chan,val,val2,mask);
 if (chan->type!=IIO_TEMP || mask!=IIO_CHAN_INFO_PROCESSED) return -EINVAL;
 mutex_lock(&sample_lock);
 ret=bridge_read(&cache,G965N_IIO_PRESSURE,1,ktime_get_boottime_ns(),&sample);
 mutex_unlock(&sample_lock);
 if (ret) return ret;
 *val=sample*10; /* SSP centi-C to IIO millicelsius. */
 return IIO_VAL_INT;
}
static const struct iio_info pressure_info = { .read_raw=read_pressure };
static int register_sensor(u32 type)
{
 struct iio_dev *dev, **target;
 const struct iio_chan_spec *channels;
 const char *name;
 unsigned int count;
 int ret;
 switch (type) {
 case G965N_IIO_ACCEL:
  if (!enable_accel) return -EACCES;
  target=&accel_dev;name="g965n-ssp-accel";channels=accel_channels;count=ARRAY_SIZE(accel_channels);
  break;
 case G965N_IIO_LIGHT:
  target=&light_dev;name="g965n-ssp-light";channels=light_channels;count=ARRAY_SIZE(light_channels);
  break;
 case G965N_IIO_PRESSURE:
  if (!enable_pressure) return -EACCES;
  target=&pressure_dev;name="g965n-ssp-pressure";channels=pressure_channels;count=ARRAY_SIZE(pressure_channels);
  break;
 case G965N_IIO_PROXIMITY:
  if (!enable_proximity) return -EACCES;
  target=&proximity_dev;name="g965n-ssp-proximity";channels=proximity_channels;count=ARRAY_SIZE(proximity_channels);
  break;
 case G965N_IIO_GYRO:
  if (!enable_gyro) return -EACCES;
  target=&gyro_dev;name="g965n-ssp-gyro";channels=gyro_channels;count=ARRAY_SIZE(gyro_channels);
  break;
 case G965N_IIO_THERMISTOR:
  if (!enable_thermistor) return -EACCES;
  target=&thermistor_dev;name="g965n-ssp-thermistor";channels=thermistor_channels;count=ARRAY_SIZE(thermistor_channels);
  break;
 default: return -EINVAL;
 }
 if (*target) return 0;
 dev=iio_device_alloc(bridge_misc.this_device,0);
 if (!dev) return -ENOMEM;
 dev->name=name;
 dev->info=type==G965N_IIO_PRESSURE?&pressure_info:&sample_info;
 dev->modes=INDIO_DIRECT_MODE;
 dev->channels=channels;
 dev->num_channels=count;
 ret=iio_device_register(dev);
 if (ret) {iio_device_free(dev);return ret;}
#ifdef CONFIG_IIO
 ret=register_hwmon(dev,type);
 if (ret) {iio_device_unregister(dev);iio_device_free(dev);return ret;}
#endif
 *target=dev;return 0;
}
static int bridge_open(struct inode *inode,struct file *file)
{
 int ret=0;
 if (!capable(CAP_SYS_ADMIN)) return -EPERM;
 if ((file->f_flags&O_ACCMODE)!=O_WRONLY) return -EACCES;
 ret=stream_open(inode,file);
 if (ret) return ret;
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
 if (decoded.type==G965N_IIO_HEADING) {
  if (decoded.value[0]==G965N_IIO_HEADING_UNAVAILABLE) {
   remove_heading();
  } else {
   ret=publish_heading(decoded.value[0]);
   if (ret) goto out;
  }
 }
 mutex_lock(&sample_lock);old=cache;bridge_update(&cache,&decoded,ktime_get_boottime_ns());mutex_unlock(&sample_lock);
 if (decoded.type!=G965N_IIO_HEARTBEAT && decoded.type!=G965N_IIO_HEADING) {
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
 mutex_lock(&sample_lock);memset(&cache,0,sizeof(cache));mutex_unlock(&sample_lock);
 /* Never hold sample_lock across kernfs/IIO removal: active read_raw may use it. */
 remove_heading();
#ifdef CONFIG_IIO
 remove_hwmon(pressure_dev,&barometer_hwmon);
 remove_hwmon(thermistor_dev,&board_hwmon);
#endif
 if (light_dev) {iio_device_unregister(light_dev);iio_device_free(light_dev);light_dev=NULL;}
 if (accel_dev) {iio_device_unregister(accel_dev);iio_device_free(accel_dev);accel_dev=NULL;}
 if (pressure_dev) {iio_device_unregister(pressure_dev);iio_device_free(pressure_dev);pressure_dev=NULL;}
 if (proximity_dev) {iio_device_unregister(proximity_dev);iio_device_free(proximity_dev);proximity_dev=NULL;}
 if (gyro_dev) {iio_device_unregister(gyro_dev);iio_device_free(gyro_dev);gyro_dev=NULL;}
 if (thermistor_dev) {iio_device_unregister(thermistor_dev);iio_device_free(thermistor_dev);thermistor_dev=NULL;}
 writer_open=false;
 mutex_unlock(&lifecycle_lock);return 0;
}
static const struct file_operations bridge_fops = {
 .owner=THIS_MODULE,.open=bridge_open,.write=bridge_write,.release=bridge_close,.llseek=NULL
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

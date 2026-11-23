// SPDX-License-Identifier: GPL-2.0-only
/* Guarded MAX77705 hardware watchdog through the existing driver's regmap.
 * Register facts derived from Samsung max77705 charger driver:
 * Copyright (C) 2012 Samsung Electronics, GPL version2.
 * Pinned reference: experiments/charging/REFERENCE.json.
 * Never changes CHG intent, CV, CC, source contract or firmware.
 */
#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/of.h>
#include <linux/regmap.h>
#include <linux/mutex.h>
#include <linux/mfd/max77705-private.h>
#include <linux/power/max77705_charger.h>
/* The existing regmap already adds CHG_REG_BASE: use its logical indices. */
#define CNFG0 MAX77705_CHG_REG_CNFG_00
#define CNFG6 MAX77705_CHG_REG_CNFG_06
#define DETAILS1 MAX77705_CHG_REG_DETAILS_01
#define WDT_EN MAX77705_WDTEN_MASK
static bool enable_g965n,armed,expiry_seen,ready;
static struct device *target;
static DEFINE_MUTEX(wdt_lock);
module_param(enable_g965n,bool,0400);

/* Caller holds target's device lock, preventing stale devm regmap access. */
static struct regmap *owned_map(void)
{
 struct i2c_client *c=i2c_verify_client(target);
 if(!c || c->addr!=0x69 || !target->driver ||
    strcmp(target->driver->name,"max77705-charger"))return NULL;
 return dev_get_regmap(target,NULL);
}
static bool healthy(unsigned int details)
{
 unsigned int charge=details&15,battery=(details>>4)&7;
 return (charge<=4 || charge==8) && (battery==1 || battery==3 || battery==4);
}
static int feed_set(const char *value,const struct kernel_param *kp)
{
 struct regmap *map;unsigned int mode,details;bool next;int ret=kstrtobool(value,&next);
 if(ret)return ret;
 mutex_lock(&wdt_lock);
 if(!ready || !target){mutex_unlock(&wdt_lock);return -ENODEV;}
 device_lock(target);
 map=owned_map();if(!map){ret=-ENODEV;goto out;}
 ret=regmap_read(map,CNFG0,&mode);if(ret)goto out;
 if(!next) {
  if(!armed){ret=0;goto out;} /* Preserve an unowned watchdog. */
  /* Clearing WDT_EN can clear the fault and resume a retained CHG request.
   * Require the real charger policy to inhibit CHG before any disarm. */
  if(mode&1){ret=-EBUSY;goto out;}
  ret=regmap_update_bits(map,CNFG0,WDT_EN,0);
  if(!ret)ret=regmap_read(map,CNFG0,&mode);
  if(!ret && (mode&WDT_EN))ret=-EIO;
  if(!ret){armed=false;module_put(THIS_MODULE);}
  goto out;
 }
 ret=regmap_read(map,DETAILS1,&details);if(ret)goto out;
 if(armed && (details&15)==11)expiry_seen=true;
 if(armed && expiry_seen){ret=-EPERM;goto out;}
 if(!healthy(details)){ret=-EPERM;goto out;} /* No blind fault reset/kick. */
 if((armed && !(mode&WDT_EN)) || (!armed && (mode&WDT_EN))) {ret=-EBUSY;goto out;}
 if(!armed) {
  if(mode&1){ret=-EBUSY;goto out;} /* Arm before allowing battery charging. */
  if(!try_module_get(THIS_MODULE)){ret=-ENODEV;goto out;}
  expiry_seen=false;
  armed=true; /* Keep cleanup ownership after any partial enable. */
  ret=regmap_update_bits(map,CNFG0,WDT_EN,WDT_EN);
  if(!ret)ret=regmap_read(map,CNFG0,&mode);
  if(!ret && !(mode&WDT_EN))ret=-EIO;
 }
 /* WDTCLR is a command: force every write even if its readback stays1. */
 if(!ret)ret=regmap_write_bits(map,CNFG6,3,1);
 out:device_unlock(target);mutex_unlock(&wdt_lock);return ret;
}
static const struct kernel_param_ops feed_ops={.set=feed_set,.get=param_get_bool};
module_param_cb(feed,&feed_ops,&armed,0600);
static int status_get(char *buffer,const struct kernel_param *kp)
{
 struct regmap *map;unsigned int mode,details;int ret;
 mutex_lock(&wdt_lock);
 if(!ready || !target){mutex_unlock(&wdt_lock);return -ENODEV;}
 device_lock(target);
 map=owned_map();if(!map){ret=-ENODEV;goto out;}
 ret=regmap_read(map,CNFG0,&mode);if(ret)goto out;
 ret=regmap_read(map,DETAILS1,&details);if(ret)goto out;
 if(armed && (details&15)==11)expiry_seen=true;
 ret=scnprintf(buffer,PAGE_SIZE,"{\"owned\":%u,\"wdt_enabled\":%u,\"charge_enabled\":%u,\"details1\":%u,\"owned_expiry_seen\":%u}\n",armed,!!(mode&WDT_EN),mode&1,details,expiry_seen);
 out:device_unlock(target);mutex_unlock(&wdt_lock);return ret;
}
static const struct kernel_param_ops status_ops={.get=status_get};
module_param_cb(status,&status_ops,NULL,0400);
static int __init start(void)
{
 struct regmap *map;unsigned int mode;int ret=0;
 if(!enable_g965n || !of_machine_is_compatible("samsung,star2lte"))return -EPERM;
 target=bus_find_device_by_name(&i2c_bus_type,NULL,"3-0069");if(!target)return -ENODEV;
 device_lock(target);map=owned_map();
 if(!map)ret=-ENODEV;
 else {
  ret=regmap_read(map,CNFG0,&mode);
  if(!ret && (mode&WDT_EN))ret=-EBUSY;
 }
 device_unlock(target);
 if(ret){put_device(target);target=NULL;}
 else ready=true;
 return ret;
}
static void __exit stop(void)
{
 /* The armed reference prevents normal unload; never silently clear a fault. */
 mutex_lock(&wdt_lock);ready=false;
 put_device(target);target=NULL;
 mutex_unlock(&wdt_lock);
}
module_init(start);module_exit(stop);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SM-G965N owned MAX77705 hardware watchdog qualification");

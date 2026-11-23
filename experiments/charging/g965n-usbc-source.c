// SPDX-License-Identifier: GPL-2.0-only
/* Read-only MAX77705 source diagnosis through its existing I2C client.
 * Register/CCI facts: Samsung Electronics and Maxim Integrated Products,
 * 2017, LineageOS exynos9810 6a9461f9460ca51d1217e5069a5d5556fcc79e63,
 * include/linux/ccic/max77705.h and drivers/ccic/max77705_cc.c.
 * Never reads clear-on-read IRQs, sends opcodes, changes roles or writes ICs.
 */
#include <linux/module.h>
#include <linux/i2c.h>
#include <linux/of.h>
static bool enable_g965n;
module_param(enable_g965n,bool,0400);
static struct device *target;
static int source(char *buffer,const struct kernel_param *kp)
{
 struct i2c_client *c;int bc,cc0,cc1,pd1,vbus,ret;
 if(!target)return -ENODEV;
 device_lock(target);
 if(!target->driver || strcmp(target->driver->name,"s9p-max77705-muic")) {ret=-ENODEV;goto out;}
 c=i2c_verify_client(target);
 if(!c || c->addr!=0x25) {ret=-ENODEV;goto out;}
 bc=i2c_smbus_read_byte_data(c,0x08);
 cc0=i2c_smbus_read_byte_data(c,0x0a);
 cc1=i2c_smbus_read_byte_data(c,0x0b);
 pd1=i2c_smbus_read_byte_data(c,0x0d);
 vbus=i2c_smbus_read_byte_data(c,0x06);
 if(bc<0 || cc0<0 || cc1<0 || pd1<0 || vbus<0) {ret=-EIO;goto out;}
 ret=scnprintf(buffer,PAGE_SIZE,"{\"bc\":%d,\"cc0\":%d,\"cc1\":%d,\"pd1\":%d,\"usbc1\":%d,\"vbus_detected\":%d,\"bc_type\":%d,\"cc_state\":%d,\"cci_code\":%d}\n",bc,cc0,cc1,pd1,vbus,!!(bc&0x80),bc&3,cc0&7,(cc0>>4)&3);
out:device_unlock(target);return ret;
}
static const struct kernel_param_ops ops={.get=source};
module_param_cb(source,&ops,NULL,0400);
static int __init start(void)
{
 if(!enable_g965n || !of_machine_is_compatible("samsung,star2lte"))return -EPERM;
 target=bus_find_device_by_name(&i2c_bus_type,NULL,"3-0025");
 if(!target)return -ENODEV;
 if(!target->driver || strcmp(target->driver->name,"s9p-max77705-muic")) {put_device(target);target=NULL;return -ENODEV;}
 return 0;
}
static void __exit stop(void){put_device(target);}
module_init(start);module_exit(stop);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("SM-G965N read-only USB-C power source status");

/* SPDX-License-Identifier: GPL-2.0-only */
static int iio_device_register(struct iio_dev *p)
{
 int v,v2;assert(lifecycle_lock.locked&&!sample_lock.locked);
 if(registration_fail)return -EIO;
 /* Device cannot advertise data/scale until its first real sample is ready. */
 if(p->channels[0].type==IIO_ACCEL){assert(p->info->read_raw(p,p->channels,&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT);assert(p->info->read_raw(p,p->channels,&v,&v2,IIO_CHAN_INFO_SCALE)==IIO_VAL_INT_PLUS_NANO&&v==0&&v2==2394202);}
 else if(p->channels[0].type==IIO_PRESSURE){
  assert(p->info->read_raw(p,p->channels,&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&v==4161524);
  assert(p->info->read_raw(p,p->channels,&v,&v2,IIO_CHAN_INFO_SCALE)==IIO_VAL_FRACTIONAL&&v==1&&v2==40960);
  assert(p->info->read_raw(p,&p->channels[1],&v,&v2,IIO_CHAN_INFO_PROCESSED)==-ENODATA);
 }
 else if(p->channels[0].type==IIO_PROXIMITY){
  char buf[16];
  assert(p->info->read_raw(p,p->channels,&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&v==0);
  assert(p->channels[0].ext_info->read(p,0,p->channels,buf)==2&&!strcmp(buf,"1\n"));
 }
 else if(p->channels[0].type==IIO_ANGL_VEL){
  assert(p->info->read_raw(p,&p->channels[0],&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&v==-65536);
  assert(p->info->read_raw(p,&p->channels[1],&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&v==0);
  assert(p->info->read_raw(p,&p->channels[2],&v,&v2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&v==131072);
  assert(p->info->read_raw(p,p->channels,&v,&v2,IIO_CHAN_INFO_SCALE)==-EINVAL);
 }
 else if(p->channels[0].type==IIO_TEMP){
  assert(p->channels[0].indexed&&p->channels[1].indexed);
  assert(p->info->read_raw(p,&p->channels[0],&v,&v2,IIO_CHAN_INFO_PROCESSED)==IIO_VAL_INT&&v==-20000);
  assert(p->info->read_raw(p,&p->channels[1],&v,&v2,IIO_CHAN_INFO_PROCESSED)==IIO_VAL_INT&&v==90000);
 }
 else assert(p->info->read_raw(p,p->channels,&v,&v2,IIO_CHAN_INFO_PROCESSED)==IIO_VAL_INT);
 registrations++;return 0;
}
static void iio_device_unregister(struct iio_dev *p)
{
 int v,v2;assert(lifecycle_lock.locked&&!sample_lock.locked);
 /* Simulate an active kernfs reader while teardown waits: no deadlock/UAF. */
 int type=p->channels[0].type;
 assert(p->info->read_raw(p,p->channels,&v,&v2,
     type==IIO_LIGHT||type==IIO_TEMP?IIO_CHAN_INFO_PROCESSED:IIO_CHAN_INFO_RAW)==-ENODATA);
 unregistrations++;
}
static struct g965n_iio_frame frame(unsigned type,unsigned seq)
{
 struct g965n_iio_frame p={0};p.version=bridge_le32(1);p.size=bridge_le32(48);p.type=bridge_le32(type);p.seq=bridge_le64(seq);return p;
}
int main(void)
{
 struct file file={.f_flags=O_WRONLY,.f_mode=FMODE_LSEEK|FMODE_PREAD|FMODE_PWRITE|FMODE_ATOMIC_POS},bad={.f_flags=O_RDWR};int val=7,val2;
 assert(bridge_init()==-ENODEV);enable_g965n=true;board=false;assert(bridge_init()==-ENODEV);board=true;chip=false;assert(bridge_init()==-ENODEV);chip=true;
 /* Default ALS-only requires no matrix and can never accept acceleration. */
 assert(!enable_accel&&!accel_matrix_count);assert(!bridge_init());
 assert(!bridge_open(NULL,&file));
 assert(stream_opens==1&&file.f_mode==FMODE_STREAM&&bridge_fops.llseek==NULL);
 struct g965n_iio_frame disabled=frame(1,1);disabled.flags=bridge_le32(1);
 assert(bridge_write(&file,(const char *)&disabled,48,NULL)==-EACCES);
 assert(!cache.seq&&!cache.heartbeat&&!cache.accel.valid&&!cache.light.valid&&!accel_dev);
 disabled.flags=0;assert(bridge_write(&file,(const char *)&disabled,48,NULL)==-EACCES);
 assert(register_sensor(G965N_IIO_ACCEL)==-EACCES&&!accel_dev);
 disabled=frame(2,1);disabled.value[0]=bridge_le32(12);
 assert(bridge_write(&file,(const char *)&disabled,48,NULL)==48);
 assert(light_dev&&!accel_dev);
 u64 prior_heartbeat=cache.heartbeat;disabled=frame(1,2);disabled.flags=bridge_le32(1);
 assert(bridge_write(&file,(const char *)&disabled,48,NULL)==-EACCES);
 assert(cache.seq==1&&cache.heartbeat==prior_heartbeat&&!cache.accel.valid&&cache.light.value[0]==12);
 disabled=frame(G965N_IIO_PRESSURE,2);disabled.value[0]=bridge_le32(4161524);
 assert(bridge_write(&file,(const char *)&disabled,48,NULL)==-EACCES);
 assert(cache.seq==1&&!cache.pressure.valid&&!pressure_dev);
 disabled=frame(G965N_IIO_PROXIMITY,2);
 assert(bridge_write(&file,(const char *)&disabled,48,NULL)==-EACCES);
 assert(cache.seq==1&&!cache.proximity.valid&&!proximity_dev);
 disabled=frame(G965N_IIO_GYRO,2);
 assert(bridge_write(&file,(const char *)&disabled,48,NULL)==-EACCES);
 assert(cache.seq==1&&!cache.gyro.valid&&!gyro_dev);
 disabled=frame(G965N_IIO_THERMISTOR,2);
 assert(bridge_write(&file,(const char *)&disabled,48,NULL)==-EACCES);
 assert(cache.seq==1&&!cache.thermistor.valid&&!thermistor_dev);
 assert(!bridge_close(NULL,&file));bridge_exit();
 assert(frees==allocations);allocations=registrations=unregistrations=frees=0;
 enable_accel=true;enable_pressure=true;enable_proximity=true;enable_gyro=true;enable_thermistor=true;
 assert(bridge_init()==-EINVAL);accel_matrix_count=9;accel_matrix[0]=accel_matrix[4]=accel_matrix[8]=1;assert(!bridge_init());assert(misc_registered==1&&!accel_dev&&!light_dev&&!pressure_dev&&!proximity_dev&&!gyro_dev);
 unsigned int before_opens=stream_opens;
 cap=false;assert(bridge_open(NULL,&file)==-EPERM);cap=true;assert(bridge_open(NULL,&bad)==-EACCES);
 assert(stream_opens==before_opens);
 assert(!bridge_open(NULL,&file));assert(bridge_open(NULL,&file)==-EBUSY);
 assert(read_sample(NULL,accel_channels,&val,&val2,IIO_CHAN_INFO_RAW)==-ENODATA&&val==7);
 struct g965n_iio_frame p=frame(1,1);p.flags=bridge_le32(1);p.value[0]=bridge_le32((u32)-5);
 int old_copy=copy_count;assert(bridge_write(&file,(const char *)&p,47,NULL)==-EMSGSIZE&&old_copy==copy_count);
 cap=false;assert(bridge_write(&file,(const char *)&p,48,NULL)==-EPERM);cap=true;copy_fail=1;assert(bridge_write(&file,(const char *)&p,48,NULL)==-EFAULT);copy_fail=0;
 allocation_fail=1;assert(bridge_write(&file,(const char *)&p,48,NULL)==-ENOMEM);assert(!cache.seq&&!cache.accel.valid&&!accel_dev);allocation_fail=0;
 registration_fail=1;assert(bridge_write(&file,(const char *)&p,48,NULL)==-EIO);assert(!cache.seq&&!cache.accel.valid&&!accel_dev);registration_fail=0;
 assert(bridge_write(&file,(const char *)&p,48,NULL)==48);assert(accel_dev&&registrations==1&&cache.seq==1);
 assert(read_sample(accel_dev,&accel_channels[0],&val,&val2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&val==-5);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==-ERANGE);assert(cache.seq==1);
 p=frame(2,2);p.value[0]=bridge_le32(100);assert(bridge_write(&file,(const char *)&p,48,NULL)==48);assert(light_dev&&registrations==2);
 p=frame(G965N_IIO_PRESSURE,3);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==-ERANGE&&!pressure_dev);
 p.value[0]=bridge_le32(0x800000);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==-ERANGE&&!pressure_dev);
 p.value[0]=bridge_le32(4161524);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==48&&pressure_dev&&registrations==3);
 p=frame(G965N_IIO_PROXIMITY,4);p.value[0]=bridge_le32(2);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==-ERANGE&&!proximity_dev);
 p.value[0]=0;
 assert(bridge_write(&file,(const char *)&p,48,NULL)==48&&proximity_dev&&registrations==4);
 p=frame(G965N_IIO_PROXIMITY,5);p.value[0]=bridge_le32(1);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==48);
 assert(read_sample(proximity_dev,proximity_channels,&val,&val2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&val==2);
 p=frame(G965N_IIO_GYRO,6);p.flags=bridge_le32(1);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==-EINVAL&&!gyro_dev);
 p.flags=0;p.value[0]=bridge_le32((u32)-65536);p.value[2]=bridge_le32(131072);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==48&&gyro_dev&&registrations==5);
 p=frame(G965N_IIO_THERMISTOR,7);
 p.value[0]=bridge_le32((u32)-20001);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==-ERANGE&&!thermistor_dev);
 p.value[0]=bridge_le32((u32)-20000);p.value[1]=bridge_le32(90000);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==48&&thermistor_dev&&registrations==6);
 clock_ns+=G965N_FRESH_NS+1;
 assert(read_sample(accel_dev,accel_channels,&val,&val2,IIO_CHAN_INFO_RAW)==-ENODATA);
 assert(read_sample(light_dev,light_channels,&val,&val2,IIO_CHAN_INFO_PROCESSED)==-ENODATA);
 assert(read_sample(proximity_dev,proximity_channels,&val,&val2,IIO_CHAN_INFO_RAW)==-ENODATA);
 p=frame(3,8);assert(bridge_write(&file,(const char *)&p,48,NULL)==48);assert(read_sample(light_dev,light_channels,&val,&val2,IIO_CHAN_INFO_PROCESSED)==IIO_VAL_INT&&val==100);assert(read_sample(accel_dev,accel_channels,&val,&val2,IIO_CHAN_INFO_RAW)==-ENODATA);
 assert(read_sample(pressure_dev,pressure_channels,&val,&val2,IIO_CHAN_INFO_RAW)==-ENODATA);
 assert(read_sample(proximity_dev,proximity_channels,&val,&val2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&val==2);
 assert(read_sample(gyro_dev,gyro_channels,&val,&val2,IIO_CHAN_INFO_RAW)==-ENODATA);
 assert(read_sample(thermistor_dev,thermistor_channels,&val,&val2,IIO_CHAN_INFO_PROCESSED)==IIO_VAL_INT&&val==-20000);
 clock_ns=cache.thermistor.when+G965N_THERMISTOR_FRESH_NS+1;
 p=frame(3,9);assert(bridge_write(&file,(const char *)&p,48,NULL)==48);
 assert(read_sample(thermistor_dev,thermistor_channels,&val,&val2,IIO_CHAN_INFO_PROCESSED)==-ENODATA);
 p=frame(G965N_IIO_PRESSURE,10);p.value[0]=bridge_le32(4161524);
 p.flags=bridge_le32(G965N_IIO_PRESSURE_TEMP_PRESENT);
 p.value[1]=bridge_le32((u32)-325);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==48);
 assert(read_pressure(pressure_dev,&pressure_channels[1],&val,&val2,IIO_CHAN_INFO_PROCESSED)==IIO_VAL_INT&&val==-3250);
 p.seq=bridge_le64(11);p.value[1]=bridge_le32(8501);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==-ERANGE);
 p.value[1]=0;assert(bridge_write(&file,(const char *)&p,48,NULL)==48);
 assert(read_pressure(pressure_dev,&pressure_channels[1],&val,&val2,IIO_CHAN_INFO_PROCESSED)==IIO_VAL_INT&&val==0);
 clock_ns+=G965N_FRESH_NS+1;
 p=frame(3,12);assert(bridge_write(&file,(const char *)&p,48,NULL)==48);
 assert(read_pressure(pressure_dev,&pressure_channels[1],&val,&val2,IIO_CHAN_INFO_PROCESSED)==-ENODATA);
 p=frame(G965N_IIO_PRESSURE,13);p.value[0]=bridge_le32(4161524);
 assert(bridge_write(&file,(const char *)&p,48,NULL)==48);
 assert(read_pressure(pressure_dev,pressure_channels,&val,&val2,IIO_CHAN_INFO_RAW)==IIO_VAL_INT&&val==4161524);
 assert(read_pressure(pressure_dev,&pressure_channels[1],&val,&val2,IIO_CHAN_INFO_PROCESSED)==-ENODATA);
 assert(!bridge_close(NULL,&file));assert(!cache.connected&&!accel_dev&&!light_dev&&!pressure_dev&&!proximity_dev&&!gyro_dev&&!thermistor_dev&&!writer_open);assert(unregistrations==6&&frees==allocations);
 assert(!bridge_open(NULL,&file));assert(!cache.seq&&!cache.accel.valid&&!cache.light.valid);assert(!bridge_close(NULL,&file));
 bridge_exit();assert(!misc_registered);return 0;
}

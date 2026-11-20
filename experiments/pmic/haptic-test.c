// SPDX-License-Identifier: GPL-2.0-only
/* Bounded standard Linux FF_RUMBLE test; no identity/audio data is recorded. */
#define _DEFAULT_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>
#ifndef G965N_HAPTIC_IDLE_BOOST
#define G965N_HAPTIC_IDLE_BOOST 1
#endif
static int state(int expect_motor, int expect_boost) {
 FILE *f=fopen("/sys/bus/platform/devices/g965n-haptic-board/motor_state","r");
 int boost=-1;unsigned bias=0,motor=0,config=0;
 if(!f)return -1;
 int n=fscanf(f,"boost=%d bias=%u motor=%u config=%x",&boost,&bias,&motor,&config);fclose(f);
 if(n!=4)return -1;
 printf("boost=%d bias=%u motor=%u config=%02x\n",boost,bias,motor,config);fflush(stdout);
 return motor==(unsigned)expect_motor && boost==expect_boost ? 0:-1;
}
int main(int argc,char **argv) {
 if(argc!=4)return 2;
 char *end;unsigned long duration=strtoul(argv[2],&end,10);if(*end||duration<50||duration>300)return 2;
 unsigned long magnitude=strtoul(argv[3],&end,10);if(*end||magnitude<4096||magnitude>16384)return 2;
 alarm(2);
 int fd=open(argv[1],O_RDWR|O_CLOEXEC);if(fd<0){perror("open");return 3;}
 char name[128]={0};if(ioctl(fd,EVIOCGNAME(sizeof(name)),name)<0||strcmp(name,"g965n-max77705-haptic")){close(fd);return 4;}
 struct ff_effect effect={0};effect.type=FF_RUMBLE;effect.id=-1;
 effect.u.rumble.strong_magnitude=(unsigned short)magnitude;effect.replay.length=(unsigned short)duration;
 int status=5;
 if(ioctl(fd,EVIOCSFF,&effect)<0){perror("effect upload");goto done;}
 struct input_event event={0};event.type=EV_FF;event.code=effect.id;event.value=1;
 if(write(fd,&event,sizeof(event))!=sizeof(event)){perror("effect play");goto remove;}
 usleep(20000);
 int on=state(1,1);
 usleep((useconds_t)(duration*1000+50000));
 event.value=0;
 if(write(fd,&event,sizeof(event))!=sizeof(event))goto remove;
 usleep(30000);
 int off=state(0,G965N_HAPTIC_IDLE_BOOST);
 status=on||off?6:0;
remove:
 if(ioctl(fd,EVIOCRMFF,effect.id)<0){perror("effect remove");status=7;}
done:
 close(fd);usleep(20000);
 if(state(0,0))status=8;
 alarm(0);return status;
}

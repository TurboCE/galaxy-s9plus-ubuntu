// SPDX-License-Identifier: GPL-2.0-only
/* Read-only aligned 32-bit hardware diagnostics for the checked SM-G965N. */
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
static uint64_t ns(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC_RAW,&t);return (uint64_t)t.tv_sec*1000000000ull+t.tv_nsec;}
int main(void){
 int fd=open("/dev/mem",O_RDONLY|O_SYNC);if(fd<0)return 1;
 void *p=mmap(0,4096,PROT_READ,MAP_SHARED,fd,0x10510000);if(p==MAP_FAILED)return 2;
 volatile uint32_t *r=p;uint32_t reload=r[0x18/4],pre=(r[0]&255)+1,mux=(r[1]>>4)&15;
 if(reload<10||mux>4||!(r[2]&(1u<<8)))return 3;
 uint32_t previous=r[0x20/4];uint64_t t0=ns(),previous_t=t0,dt=0,ticks=0,samples=0;
 while(ns()-t0<50000000){
  uint32_t value=r[0x20/4];uint64_t now=ns(),elapsed=now-previous_t;
  if(elapsed&&elapsed<20000&&previous<=reload&&value<=reload){
   ticks+=(previous>=value)?previous-value:previous+reload+1-value;dt+=elapsed;samples++;
  }
  previous=value;previous_t=now;
 }
 if(!dt||samples<100)return 4;
 double rate=(double)ticks*1e9/dt*pre*(1u<<mux);
 printf("source_hz=%.0f reload=%u prescaler=%u divider=%u samples=%llu\n",rate,reload,pre,1u<<mux,(unsigned long long)samples);
 munmap(p,4096);close(fd);return rate>25000000&&rate<27000000?0:5;
}

// SPDX-License-Identifier: GPL-2.0-only
/* Read only the two reviewed motor GPIO pads with aligned 32-bit MMIO. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <unistd.h>
int main(void){int fd=open("/dev/mem",O_RDONLY|O_SYNC);if(fd<0)return 1;void*p=mmap(0,4096,PROT_READ,MAP_SHARED,fd,0x10430000);if(p==MAP_FAILED)return 2;volatile uint32_t*r=p;printf("pad_function=%u pad_value=%u boost_function=%u boost_value=%u\n",(r[0x60/4]>>4)&15,(r[0x64/4]>>1)&1,(r[0xa0/4]>>28)&15,(r[0xa4/4]>>7)&1);munmap(p,4096);close(fd);return 0;}

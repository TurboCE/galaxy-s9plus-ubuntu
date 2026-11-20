// SPDX-License-Identifier: GPL-2.0-only
/* Read-only aligned 32-bit hardware diagnostics for the checked SM-G965N. */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>
static volatile uint32_t *map;
static uint32_t rd(uint32_t off) {
 if((off&3)||off<0x3000||off>0x2fffc)exit(3);
 return map[(off-0x3000)/4];
}
static unsigned int byte(uint32_t off) {return (rd(off&~3u)>>((off&3)*8))&255;}
static unsigned int half(uint32_t off) {
 if(off&1)exit(4);
 return (rd(off&~3u)>>((off&2)*8))&65535;
}
int main(void) {
 int fd=open("/dev/mem",O_RDONLY|O_SYNC);
 if(fd<0)return 1;
 void *p=mmap(0,0x2d000,PROT_READ,MAP_SHARED,fd,0x0203c000);
 if(p==MAP_FAILED)return 2;
 map=p;
 uint32_t plugins=rd(0x7f00),count=rd(0x7f04);
 if(count<1||count>32)return 5;
 for(uint32_t i=0;i<count;i++) {
  uint32_t row=plugins+i*48,np=rd(row+44);char name[65]={0};
  if(!np)continue;
  for(unsigned int j=0;j<64;j++){name[j]=(char)byte(np+j);if(!name[j])break;}
  int match=0;
  for(unsigned int j=0;j+3<64&&name[j];j++)
   if((name[j]=='d'||name[j]=='D')&&(name[j+1]=='v'||name[j+1]=='V')&&(name[j+2]=='f'||name[j+2]=='F')&&(name[j+3]=='s'||name[j+3]=='S'))match=1;
  if(!match)continue;
  if(byte(row+32)!=1||byte(row+40)!=1)return 6;
  uint32_t fv=(rd(row+4)&~1u)+0x6700;
  printf("fvmap=%x\n",fv);
  for(unsigned int j=0;j<13;j++) {
   uint32_t h=fv+j*24;unsigned int lv=byte(h+1),n=byte(h+2),pll=byte(h+3),members=half(h+18);
   if(lv>100||pll>n)return 7;
   printf("domain=%u levels=%u members=%u pll=%u addresses=",j,lv,n,pll);
   for(unsigned int k=0;k<pll;k++)printf("%s%x",k?",":"",rd(fv+half(fv+members+2*k)));
   printf("\n");
  }
 }
 munmap(p,0x2d000);close(fd);return 0;
}

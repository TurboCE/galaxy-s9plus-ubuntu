// SPDX-License-Identifier: GPL-2.0-only
/* Original dependency-only interoperability probe. No RIL_Init call.
 * The owner's Bionic loader/libc ABI supplies program startup; no proprietary
 * implementation or startup object is copied. Never publish owner libraries.
 */
#include <stddef.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <linux/prctl.h>
#include <asm/unistd.h>

extern long syscall(long, ...);
extern int prctl(int, ...);
extern int printf(const char *, ...);
extern int fflush(void *);
extern int strcmp(const char *, const char *);
extern void *dlopen(const char *, int);
extern void *dlsym(void *, const char *);
extern char *dlerror(void);
#ifdef G965N_PROBE_HOST_TEST
extern int *__errno_location(void);
#define probe_errno (*__errno_location())
#else
extern int *__errno(void);
#define probe_errno (*__errno())
#endif
#define EPERM_VALUE 1
#define AT_FDCWD_VALUE -100
#define READ_WRITE_FLAGS (1U|2U|64U|128U|512U|1024U|0x400000U)
#define ALLOW SECCOMP_RET_ALLOW
#define DENY (SECCOMP_RET_ERRNO|EPERM_VALUE)
#define NR(n) BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,__NR_##n,0,1),BPF_STMT(BPF_RET|BPF_K,ALLOW)
#define ARG_LO(n) (offsetof(struct seccomp_data,args)+(n)*8)
#define ARG_HI(n) (ARG_LO(n)+4)
#if defined(__aarch64__)
#define PROBE_ARCH AUDIT_ARCH_AARCH64
#elif defined(__x86_64__) && defined(G965N_PROBE_HOST_TEST)
#define PROBE_ARCH AUDIT_ARCH_X86_64
#else
#error Unsupported syscall ABI
#endif
/* Every permitted FD is initially a stdio stream or a read-only file. No
 * filesystem mutation, device ioctl, socket, exec, ptrace, or mount syscall is
 * allowed. The filter remains installed through constructors and termination.
 */
static int readonly_filter(void)
{
 struct sock_filter instructions[]={
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,arch)),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,PROBE_ARCH,1,0),
  BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_KILL_PROCESS),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr)),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,__NR_openat,0,4),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,ARG_LO(2)),
  BPF_JUMP(BPF_JMP|BPF_JSET|BPF_K,READ_WRITE_FLAGS,0,1),
  BPF_STMT(BPF_RET|BPF_K,DENY),BPF_STMT(BPF_RET|BPF_K,ALLOW),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,__NR_write,0,5),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,ARG_LO(0)),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,1,2,0),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,2,1,0),
  BPF_STMT(BPF_RET|BPF_K,DENY),BPF_STMT(BPF_RET|BPF_K,ALLOW),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,__NR_writev,0,5),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,ARG_LO(0)),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,1,2,0),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,2,1,0),
  BPF_STMT(BPF_RET|BPF_K,DENY),BPF_STMT(BPF_RET|BPF_K,ALLOW),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,__NR_fcntl,0,6),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,ARG_LO(1)),
  BPF_JUMP(BPF_JMP|BPF_JGT|BPF_K,4,1,0),BPF_STMT(BPF_RET|BPF_K,ALLOW),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,1030,1,0),
  BPF_STMT(BPF_RET|BPF_K,DENY),BPF_STMT(BPF_RET|BPF_K,ALLOW),
#ifdef __NR_prlimit64
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,__NR_prlimit64,0,7),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,ARG_LO(2)),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,0,1,0),BPF_STMT(BPF_RET|BPF_K,DENY),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,ARG_HI(2)),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,0,1,0),BPF_STMT(BPF_RET|BPF_K,DENY),
  BPF_STMT(BPF_RET|BPF_K,ALLOW),
#endif
  NR(read),NR(readv),NR(pread64),NR(lseek),NR(close),NR(fstat),NR(newfstatat),
  NR(statfs),NR(fstatfs),
  NR(readlinkat),NR(getdents64),NR(getcwd),NR(faccessat),NR(dup),NR(dup3),
  NR(mmap),NR(mprotect),NR(munmap),NR(brk),NR(madvise),NR(futex),NR(sched_yield),
  NR(sched_getaffinity),NR(rt_sigaction),NR(rt_sigprocmask),NR(rt_sigreturn),NR(sigaltstack),
  NR(clock_gettime),NR(clock_getres),NR(clock_nanosleep),NR(nanosleep),NR(gettimeofday),
  NR(getpid),NR(getppid),NR(gettid),NR(getuid),NR(geteuid),NR(getgid),NR(getegid),
  NR(getresuid),NR(getresgid),NR(uname),NR(sysinfo),NR(prctl),
  NR(set_tid_address),NR(set_robust_list),NR(getrandom),NR(restart_syscall),
  NR(exit),NR(exit_group),
#ifdef __NR_getrlimit
  NR(getrlimit),
#endif
#ifdef __NR_statx
  NR(statx),
#endif
#ifdef __NR_faccessat2
  NR(faccessat2),
#endif
#ifdef __NR_rseq
  NR(rseq),
#endif
#ifdef __NR_membarrier
  NR(membarrier),
#endif
  BPF_STMT(BPF_RET|BPF_K,DENY)
 };
 struct sock_fprog program={sizeof(instructions)/sizeof(instructions[0]),instructions};
 if(prctl(PR_SET_NO_NEW_PRIVS,1UL,0UL,0UL,0UL))return -1;
 return prctl(PR_SET_SECCOMP,(unsigned long)SECCOMP_MODE_FILTER,&program,0UL,0UL);
}
static int denied(long result){return result==-1 && probe_errno==EPERM_VALUE;}
static int self_test(void)
{
 unsigned long commands[]={0x6f19,0x6f20,0x6f21,0x6f22,0x6f27,0x541b};
 for(unsigned i=0;i<sizeof(commands)/sizeof(commands[0]);i++)
  if(!denied(syscall(__NR_ioctl,-1L,commands[i],0UL)))return 10;
 if(!denied(syscall(__NR_openat,AT_FDCWD_VALUE,"/data/g965n-probe-forbidden",65,0600)))return 11;
 if(!denied(syscall(__NR_write,-1L,"x",1UL)))return 12;
 if(!denied(syscall(__NR_socket,1,1,0)))return 13;
 if(!denied(syscall(__NR_unlinkat,AT_FDCWD_VALUE,"/data/g965n-probe-forbidden",0)))return 14;
 if(!denied(syscall(__NR_fcntl,-1L,8,1)))return 15; /* F_SETOWN */
 if(!denied(syscall(__NR_pwrite64,-1L,"x",1UL,0UL)))return 16;
 unsigned long fs_info[32];
 if(syscall(__NR_fstatfs,0,fs_info)!=0)return 17;
 printf("{\"readonly_self_test\":true,\"ril_init_called\":false}\n");
 return 0;
}
int probe_main(int argc,char **argv,char **envp)
{
 (void)envp;
 if(argc!=2 || (strcmp(argv[1],"--self-test") && strcmp(argv[1],"--inspect")))return 2;
 if(readonly_filter())return 3;
 if(!strcmp(argv[1],"--self-test"))return self_test();
 void *library=dlopen("/vendor/lib64/libsec-ril.so",2);
 if(!library){printf("{\"library_loaded\":false,\"ril_init_called\":false}\n");
  char *error=dlerror();if(error)printf("private_loader_error: %s\n",error);return 4;}
 int present=dlsym(library,"RIL_Init")!=0;
 printf("{\"library_loaded\":true,\"ril_entry_present\":%s,\"ril_init_called\":false}\n",present?"true":"false");
 return present?0:5;
}
#ifdef G965N_PROBE_HOST_TEST
int main(int argc,char **argv,char **envp){int r=probe_main(argc,argv,envp);fflush(0);return r;}
#else
/* The verified owner ABI reads the fini-array pointer at vector offset16.
 * No executable constructors/destructors are supplied by this original probe.
 */
__attribute__((visibility("hidden"))) unsigned long probe_ctors[3];
__asm__(".text\n.align 2\n.global _start\n.type _start,%function\n_start:\n"
 "mov x0,sp\nmov x1,xzr\nadrp x2,probe_main\nadd x2,x2,:lo12:probe_main\n"
 "adrp x3,probe_ctors\nadd x3,x3,:lo12:probe_ctors\nb __libc_init\n");
#endif

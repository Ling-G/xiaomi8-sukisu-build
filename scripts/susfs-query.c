/* SPDX-License-Identifier: GPL-2.0-only
 * Read-only ARM64 SUSFS v2 query probe. This is not a replacement for ksu_susfs.
 * Protocol: SUSFS v2.3.0 susfs.h / susfs_def.h at the pinned source revision.
 */
typedef unsigned long size_t;
static long sys4(long nr,long a,long b,long c,long d)
{
 register long x0 __asm__("x0")=a,x1 __asm__("x1")=b;
 register long x2 __asm__("x2")=c,x3 __asm__("x3")=d;
 register long x8 __asm__("x8")=nr;
 __asm__ volatile("svc #0":"+r"(x0):"r"(x1),"r"(x2),"r"(x3),"r"(x8):"memory","cc");
 return x0;
}
static size_t length(const char *s){size_t n=0;while(s[n])n++;return n;}
static void print(const char *s){sys4(64,1,(long)s,length(s),0);}
static struct {char data[16];int err;} version,variant;
static struct {char data[8192];int err;} features;
static int query(unsigned cmd,void *p,int *err)
{
 *err=-1;
 if(sys4(142,0xDEADBEEF,0xFAFAFAFA,cmd,(long)p)||*err)return 1;
 return 0;
}
int main_start(long *stack)
{
 (void)stack;
 if(sys4(174,0,0,0,0)!=0){print("Root required\n");return 1;}
 if(query(0x555e1,&version,&version.err)||query(0x555e3,&variant,&variant.err)||query(0x555e2,&features,&features.err)){
  print("SUSFS v2 query failed or unsupported\n");return 1;
 }
 version.data[15]=0;variant.data[15]=0;features.data[8191]=0;
 print("SUSFS version: ");print(version.data);print("\nVariant: ");print(variant.data);
 print("\nEnabled features:\n");print(features.data);print("\n");return 0;
}
__asm__(".text\n.global _start\n_start:\nmov x0, sp\nbl main_start\nmov x8, #93\nsvc #0\n");

/* Standalone AArch64 client or read-only discovery tracing interposer. */
#ifdef VT_DISCOVERY_TRACE
extern void *dlsym(void *, const char *);
extern int snprintf(char *, unsigned long, const char *, ...);
static long raw4(long nr, long a, long b, long c, long d)
{
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    register long x8 __asm__("x8") = nr;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x3), "r"(x8) : "memory", "cc");
    return x0;
}
static int prefix(const char *a, const char *b)
{
    while (*b) { if (*a++ != *b++) return 0; }
    return 1;
}
static int active(void)
{
    char path[256];
    long n = raw4(78, -100, (long)"/proc/self/exe", (long)path, sizeof(path)-1);
    long i;
    if (n <= 0) return 0;
    path[n] = 0;
    for (i=0; i<n; ++i) if (prefix(path+i, "/VTKernel.")) return 1;
    return 0;
}
static void record(const char *action, const char *path, long result, unsigned long extra)
{
    char line[512];
    int n;
    if (!active()) return;
    n=snprintf(line,sizeof(line),"[VT-DISC] %s %s result=%ld extra=0x%lx\n",action,path?path:"-",result,extra);
    if (n>0) raw4(64,2,(long)line,n<(int)sizeof(line)?n:(int)sizeof(line)-1,0);
}
int stat(const char *path, void *buffer)
{
    int (*real)(const char *,void *)=dlsym((void *)-1L,"stat");
    int result=real(path,buffer);
    if (path && prefix(path,"/dev/")) {
        record("stat",path,result,0);
        if (!result) {
            unsigned long *words=buffer;
            record("stat-word2",path,words[2],words[3]);
            record("stat-word4",path,words[4],words[5]);
        }
    }
    return result;
}
int __open_2(const char *path, int flags)
{
    int (*real)(const char *,int)=dlsym((void *)-1L,"__open_2");
    int result=real(path,flags);
    if (path && prefix(path,"/dev/")) record("__open_2",path,result,flags);
    return result;
}
int open(const char *path, int flags, ...)
{
    int (*real)(const char *,int,...)=dlsym((void *)-1L,"open");
    __builtin_va_list args;
    unsigned int mode=0;
    int result;
    if ((flags & 0100) || ((flags & 020000000)==020000000)) {
        __builtin_va_start(args,flags);
        mode=__builtin_va_arg(args,unsigned int);
        __builtin_va_end(args);
    }
    result=real(path,flags,mode);
    if (path && prefix(path,"/dev/")) record("open",path,result,flags);
    return result;
}
void *opendir(const char *path)
{
    void *(*real)(const char *)=dlsym((void *)-1L,"opendir");
    void *result=real(path);
    if (path && prefix(path,"/dev")) record("opendir",path,(long)result,0);
    return result;
}
int ioctl(int fd, unsigned long command, ...)
{
    int (*real)(int,unsigned long,...)=dlsym((void *)-1L,"ioctl");
    __builtin_va_list args;
    unsigned long argument;
    int result;
    __builtin_va_start(args,command);
    argument=__builtin_va_arg(args,unsigned long);
    __builtin_va_end(args);
    result=real(fd,command,argument);
    record("ioctl",0,result,command);
    return result;
}
#else
/* Standalone AArch64 test client; never loads or unloads a module. */
#define VT_USERSPACE_FREESTANDING
#include "vt_protocol.h"

/* GCC may emit memcpy for constant local array initialization. */
void *memcpy(void *destination, const void *source, unsigned long count)
{
    volatile unsigned char *out = destination;
    const volatile unsigned char *in = source;
    unsigned long i;
    for (i = 0; i < count; ++i)
        out[i] = in[i];
    return destination;
}

static long syscall4(long nr, long a, long b, long c, long d)
{
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    register long x8 __asm__("x8") = nr;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x3), "r"(x8) : "memory", "cc");
    return x0;
}

static long request(long fd, unsigned int cmd, struct vt_copy_memory *r)
{
    return syscall4(29, fd, cmd, (long)r, 0);
}

static volatile char remote_data[4] = {'q', 'r', 's', 0};

static int lookup(long fd, long pid)
{
    struct vt_module_base query;
    query.pid = pid;
    query.reserved = 0;
    query.name = (unsigned long)"vt_probe_test";
    query.base = 0;
    if (syscall4(29, fd, VT_MODULE_BASE, (long)&query, 0) || !query.base)
        return 20;
    query.name = (unsigned long)"vt_probe_module_that_does_not_exist";
    query.base = 123;
    if (syscall4(29, fd, VT_MODULE_BASE, (long)&query, 0) || query.base)
        return 21;
    return 0;
}

static int remote_test(long fd)
{
    int ready[2], control[2], status = 0, result = 0;
    char token = 'R', observed[4] = {0}, replacement[4] = {'l', 'm', 'n', 0};
    struct vt_copy_memory r;
    long child;
    if (syscall4(59, (long)ready, 0, 0, 0) || syscall4(59, (long)control, 0, 0, 0))
        return 22;
    child = syscall4(220, 17, 0, 0, 0); /* fork semantics: SIGCHLD, separate mm */
    if (child == 0) {
        syscall4(57, ready[0], 0, 0, 0);
        syscall4(57, control[1], 0, 0, 0);
        syscall4(64, ready[1], (long)&token, 1, 0);
        if (syscall4(63, control[0], (long)&token, 1, 0) != 1 ||
            remote_data[0] != 'l' || remote_data[2] != 'n')
            status = 1;
        syscall4(64, ready[1], (long)&status, sizeof(status), 0);
        syscall4(94, status, 0, 0, 0);
        for (;;) {}
    }
    if (child < 0)
        return 23;
    syscall4(57, ready[1], 0, 0, 0);
    syscall4(57, control[0], 0, 0, 0);
    if (syscall4(63, ready[0], (long)&token, 1, 0) != 1) {
        result = 24;
        goto cleanup;
    }
    r.pid = child;
    r.reserved = 0;
    r.addr = (unsigned long)remote_data;
    r.buffer = (unsigned long)observed;
    r.size = sizeof(observed);
    if (request(fd, VT_MEMORY_READ, &r) || observed[0] != 'q' || observed[2] != 's') {
        result = 25;
        goto cleanup;
    }
    r.buffer = (unsigned long)replacement;
    if (request(fd, VT_MEMORY_WRITE, &r) || remote_data[0] != 'q') {
        result = 26;
        goto cleanup;
    }
    result = lookup(fd, child);
    if (result)
        goto cleanup;
    token = 'T';
    if (syscall4(64, control[1], (long)&token, 1, 0) != 1 ||
        syscall4(63, ready[0], (long)&status, sizeof(status), 0) != sizeof(status) || status)
        result = 27;
cleanup:
    if (result)
        syscall4(129, child, 9, 0, 0);
    syscall4(57, ready[0], 0, 0, 0);
    syscall4(57, control[1], 0, 0, 0);
    syscall4(260, child, 0, 0, 0);
    return result;
}

static int run(void)
{
    char source[4] = {'a', 'b', 'c', 0};
    char dest[4] = {0};
    char replacement[4] = {'x', 'y', 'z', 0};
    struct vt_copy_memory r;
    long pid = syscall4(172, 0, 0, 0, 0);
    long fd = syscall4(56, -100, (long)"/dev/vt_abi_probe", 2 | 02000000, 0);
    int result = 0;
    if (fd < 0)
        return 10;
    r.pid = pid;
    r.reserved = 0;
    r.addr = (unsigned long)source;
    r.buffer = (unsigned long)dest;
    r.size = sizeof(source);
    if (request(fd, VT_MEMORY_READ, &r) != 0 || dest[0] != 'a' || dest[2] != 'c') {
        result = 11;
        goto done;
    }
    r.buffer = (unsigned long)replacement;
    if (request(fd, VT_MEMORY_WRITE, &r) != 0 || source[0] != 'x' || source[2] != 'z') {
        result = 12;
        goto done;
    }
    r.pid = -1;
    if (request(fd, VT_MEMORY_READ, &r) != -22) {
        result = 13;
        goto done;
    }
    r.pid = pid;
    r.size = 65537;
    if (request(fd, VT_MEMORY_READ, &r) != -7) {
        result = 14;
        goto done;
    }
    if (request(fd, VT_HW_INSTALL, &r) != -95 || request(fd, 0, &r) != -22)
        result = 15;
    if (!result)
        result = lookup(fd, pid);
    if (!result)
        result = remote_test(fd);
done:
    syscall4(57, fd, 0, 0, 0);
    return result;
}

void _start(void)
{
    int result = run();
    const char success[] = "PASS: VT self/child read-write and module lookup tests\n";
    const char failure[] = "FAIL: VT diagnostic subset tests; inspect exit status\n";
    if (!result)
        syscall4(64, 1, (long)success, sizeof(success) - 1, 0);
    else
        syscall4(64, 2, (long)failure, sizeof(failure) - 1, 0);
    syscall4(94, result, 0, 0, 0);
    for (;;) {}
}
#endif

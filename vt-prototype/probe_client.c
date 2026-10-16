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
    r.pid = pid + 1;
    if (request(fd, VT_MEMORY_READ, &r) != -1) {
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
done:
    syscall4(57, fd, 0, 0, 0);
    return result;
}

void _start(void)
{
    int result = run();
    const char success[] = "PASS: VT diagnostic subset tests\n";
    const char failure[] = "FAIL: VT diagnostic subset tests; inspect exit status\n";
    if (!result)
        syscall4(64, 1, (long)success, sizeof(success) - 1, 0);
    else
        syscall4(64, 2, (long)failure, sizeof(failure) - 1, 0);
    syscall4(94, result, 0, 0, 0);
    for (;;) {}
}

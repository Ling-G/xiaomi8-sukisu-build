/* Hold the diagnostic node open so the hidden-node window can be observed.
 * Standalone AArch64 program: no libc, no module loading. */
struct vt_timespec {
    long tv_sec;
    long tv_nsec;
};

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

static void emit(const char *text, long length)
{
    syscall4(64, 1, (long)text, length, 0);
}

void _start(void)
{
    static const char failed[] = "FAIL open /dev/vt_abi_probe\n";
    static const char opened[] = "OPEN /dev/vt_abi_probe\n";
    static const char closed[] = "CLOSED /dev/vt_abi_probe\n";
    struct vt_timespec pause;
    long fd = syscall4(56, -100, (long)"/dev/vt_abi_probe", 2, 0);

    if (fd < 0) {
        emit(failed, (long)sizeof(failed) - 1);
        syscall4(94, 31, 0, 0, 0);
    }
    emit(opened, (long)sizeof(opened) - 1);
    pause.tv_sec = 5;
    pause.tv_nsec = 0;
    syscall4(101, (long)&pause, 0, 0, 0);
    syscall4(57, fd, 0, 0, 0);
    emit(closed, (long)sizeof(closed) - 1);
    syscall4(94, 0, 0, 0, 0);
    for (;;) { }
}

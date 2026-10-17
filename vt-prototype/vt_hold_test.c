/* Hold the discovery node open so the hidden-node window can be observed.
 * Standalone AArch64 program: no libc, no module loading. The node name is
 * random per load, so it is found by enumerating /dev for six alphanumeric
 * characters, exactly like the original VT client. */
struct vt_timespec {
    long tv_sec;
    long tv_nsec;
};

struct vt_dirent64 {
    unsigned long long d_ino;
    long long d_off;
    unsigned short d_reclen;
    unsigned char d_type;
    char d_name[];
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

static int six_alnum(const char *name)
{
    int i;
    for (i = 0; i < 6; ++i) {
        char c = name[i];
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') ||
              (c >= 'a' && c <= 'z')))
            return 0;
    }
    return name[6] == 0;
}

/* Returns the open descriptor and reports the path through out[12]. */
static long open_discovery_node(char *out)
{
    char buffer[2048];
    long count;
    int dirfd, i;

    dirfd = (int)syscall4(56, -100, (long)"/dev", 0x10000, 0);
    if (dirfd < 0)
        return -1;
    while ((count = syscall4(61, dirfd, (long)buffer, sizeof(buffer), 0)) > 0) {
        for (i = 0; i < count;) {
            struct vt_dirent64 *entry = (void *)(buffer + i);
            if (entry->d_reclen == 0)
                break;
            if (six_alnum(entry->d_name)) {
                int k;
                long fd;
                out[0] = '/';
                out[1] = 'd';
                out[2] = 'e';
                out[3] = 'v';
                out[4] = '/';
                for (k = 0; k < 6; ++k)
                    out[5 + k] = entry->d_name[k];
                out[11] = 0;
                fd = syscall4(56, -100, (long)out, 2, 0);
                if (fd >= 0) {
                    syscall4(57, dirfd, 0, 0, 0);
                    return fd;
                }
            }
            i += entry->d_reclen;
        }
    }
    syscall4(57, dirfd, 0, 0, 0);
    return -1;
}

void _start(void)
{
    static const char failed[] = "FAIL open discovery node\n";
    static const char opened[] = "OPEN ";
    static const char closed[] = "CLOSED ";
    char path[12];
    struct vt_timespec pause;
    long fd = open_discovery_node(path);

    if (fd < 0) {
        emit(failed, (long)sizeof(failed) - 1);
        syscall4(94, 31, 0, 0, 0);
    }
    emit(opened, (long)sizeof(opened) - 1);
    emit(path, 11);
    emit("\n", 1);
    pause.tv_sec = 5;
    pause.tv_nsec = 0;
    syscall4(101, (long)&pause, 0, 0, 0);
    syscall4(57, fd, 0, 0, 0);
    emit(closed, (long)sizeof(closed) - 1);
    emit(path, 11);
    emit("\n", 1);
    syscall4(94, 0, 0, 0, 0);
    for (;;) { }
}

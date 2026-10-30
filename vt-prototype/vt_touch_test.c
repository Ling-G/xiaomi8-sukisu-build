/* Standalone AArch64 test: syscalls only; no shell input/sendevent fallback. */
#define VT_TOUCH_FREESTANDING
#include "vt_touch_protocol.h"

struct pause_time { long seconds, nanoseconds; };

static long call4(long nr, long a, long b, long c, long d)
{
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    register long x8 __asm__("x8") = nr;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x1), "r"(x2), "r"(x3), "r"(x8) : "memory", "cc");
    return x0;
}

static void emit(const char *s)
{
    long n = 0;
    while (s[n]) ++n;
    while (n > 0) {
        long done = call4(64, 1, (long)s, n, 0);
        if (done == -4) continue;
        if (done <= 0) break;
        s += done;
        n -= done;
    }
}

static void number(unsigned long long value)
{
    char buf[24];
    int i = 23;
    buf[i] = 0;
    do { buf[--i] = '0' + value % 10; value /= 10; } while (value);
    emit(buf + i);
}

static int equal(const char *a, const char *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}

static int parse(const char *s, unsigned int *out)
{
    unsigned long long n = 0;
    if (!*s) return 0;
    while (*s) {
        if (*s < '0' || *s > '9') return 0;
        n = n * 10 + *s++ - '0';
        if (n > 0xffffffffULL) return 0;
    }
    *out = (unsigned int)n;
    return 1;
}

static long query(long fd, struct vt_touch_info *info)
{
    return call4(29, fd, VT_TOUCH_GET_INFO, (long)info, 0);
}

static int fail(const char *step, long result)
{
    emit("FAIL "); emit(step); emit(" result=");
    if (result < 0) emit("-");
    number(result < 0 ? (unsigned long long)-result : (unsigned long long)result);
    emit("\n");
    return 1;
}

/* Without --tap this test emits no valid touch events. */
static int run(long argc, char **argv)
{
    struct vt_touch_info before, after;
    struct vt_touch_click click = { 0, 0, 80, 0 };
    long fd, result;
    int tap = argc >= 2 && equal(argv[1], "--tap");

    if (!((argc == 1) || (argc == 2 && equal(argv[1], "--selftest")) ||
          (tap && (argc == 4 || argc == 5)))) {
        emit("Usage: vt_touch_test [--selftest | --tap X Y [10..1000 ms]]\n");
        return 2;
    }
    if (tap && (!parse(argv[2], &click.x) || !parse(argv[3], &click.y) ||
        (argc == 5 && !parse(argv[4], &click.duration_ms))))
        return fail("numeric arguments", -22);

    fd = call4(56, -100, (long)"/dev/vt_touch", 2 | 0x80000, 0);
    if (fd < 0) return fail("open /dev/vt_touch", fd);
    result = query(fd, &before);
    if (result || before.version != VT_TOUCH_ABI_VERSION || before.reserved ||
        before.width < 16 || before.height < 16)
        return fail("GET_INFO / ABI", result ? result : -22);
    emit("VT_TOUCH_ABI="); number(before.version);
    emit(" SIZE="); number(before.width); emit("x"); number(before.height);
    emit(" CLICKS="); number(before.completed_clicks); emit("\n");

    if (!tap) {
        struct vt_touch_click bad = { before.width, 0, 80, 0 };
        if (call4(29, fd, VT_TOUCH_CLICK, (long)&bad, 0) != -22)
            return fail("out-of-range X", -1);
        bad.x = 0; bad.y = before.height;
        if (call4(29, fd, VT_TOUCH_CLICK, (long)&bad, 0) != -22)
            return fail("out-of-range Y", -1);
        bad.y = 0; bad.duration_ms = 0;
        if (call4(29, fd, VT_TOUCH_CLICK, (long)&bad, 0) != -22)
            return fail("zero duration", -1);
        bad.duration_ms = VT_TOUCH_MAX_MS + 1;
        if (call4(29, fd, VT_TOUCH_CLICK, (long)&bad, 0) != -22)
            return fail("long duration", -1);
        bad.duration_ms = 80; bad.reserved = 1;
        if (call4(29, fd, VT_TOUCH_CLICK, (long)&bad, 0) != -22)
            return fail("reserved field", -1);
        if (call4(29, fd, VT_TOUCH_CLICK, 1, 0) != -14 ||
            call4(29, fd, VT_TOUCH_GET_INFO, 1, 0) != -14)
            return fail("invalid user pointers", -1);
        if (call4(29, fd, 0, 0, 0) != -25)
            return fail("unknown ioctl", -1);
        result = query(fd, &after);
        if (result || after.completed_clicks != before.completed_clicks)
            return fail("rejected calls changed click count", result ? result : -1);
        emit("PASS: ABI, bounds, duration, reserved, pointers, unknown ioctl; no clicks emitted\n");
    } else {
        struct pause_time pause = { 3, 0 }, remaining;
        if (click.x >= before.width || click.y >= before.height ||
            click.duration_ms < VT_TOUCH_MIN_MS || click.duration_ms > VT_TOUCH_MAX_MS)
            return fail("coordinates / duration", -22);
        emit("Single native-portrait tap in 3 seconds at ");
        number(click.x); emit(","); number(click.y); emit("\n");
        while ((result = call4(101, (long)&pause, (long)&remaining, 0, 0)) == -4)
            pause = remaining;
        if (result) return fail("countdown", result);
        result = call4(29, fd, VT_TOUCH_CLICK, (long)&click, 0);
        if (result) return fail("CLICK", result);
        result = query(fd, &after);
        if (result || after.completed_clicks != before.completed_clicks + 1)
            return fail("completed count (run without other clients)", result ? result : -1);
        emit("PASS: one press/release completed; confirm UI or capture evdev for delivery\n");
    }
    result = call4(57, fd, 0, 0, 0);
    return result ? fail("close", result) : 0;
}

void touch_start(unsigned long *stack)
{
    int result = run((long)stack[0], (char **)(stack + 1));
    call4(94, result, 0, 0, 0);
    for (;;) { }
}

__asm__(".global _start\n.type _start,%function\n_start:\nmov x0,sp\nbl touch_start\n");

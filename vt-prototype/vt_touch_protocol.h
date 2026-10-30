#ifndef VT_TOUCH_PROTOCOL_H
#define VT_TOUCH_PROTOCOL_H

/* Project extension, not a recovered VT command. Native AArch64 only. */
#ifdef VT_TOUCH_FREESTANDING
typedef unsigned int vt_touch_u32;
typedef unsigned long long vt_touch_u64;
#else
#include <linux/types.h>
typedef __u32 vt_touch_u32;
typedef __u64 vt_touch_u64;
#endif

#define VT_TOUCH_ABI_VERSION 1U
#define VT_TOUCH_GET_INFO 0x80185401U /* _IOR('T', 1, 24) */
#define VT_TOUCH_CLICK    0x40105402U /* _IOW('T', 2, 16) */
#define VT_TOUCH_MIN_MS 10U
#define VT_TOUCH_MAX_MS 1000U

struct vt_touch_info {
    vt_touch_u32 version;
    vt_touch_u32 width;
    vt_touch_u32 height;
    vt_touch_u32 reserved;
    vt_touch_u64 completed_clicks;
};

struct vt_touch_click {
    vt_touch_u32 x;
    vt_touch_u32 y;
    vt_touch_u32 duration_ms;
    vt_touch_u32 reserved;
};

#endif

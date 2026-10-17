#ifndef VT_PROTOCOL_H
#define VT_PROTOCOL_H

#ifdef VT_USERSPACE_FREESTANDING
typedef signed int __s32;
typedef unsigned int __u32;
typedef unsigned long long __u64;
typedef unsigned char __u8;
#else
#include <linux/types.h>
#endif

/* Recovered from module-7.ko; native AArch64 ABI only. */
#define VT_HW_INSTALL   0x02813441U
#define VT_HW_HITS      0x02813442U
#define VT_HW_ENABLE    0x02813443U
#define VT_HW_CLEAR     0x02813444U
#define VT_HW_DISABLE   0x02813445U
#define VT_TRACKING     0x02813446U
#define VT_MEMORY_READ  0x02813449U
#define VT_MEMORY_WRITE 0x02813450U
#define VT_MODULE_BASE  0x02813451U

/* Explicit padding preserves the observed ARM64 offsets on other hosts. */
struct vt_copy_memory {
    __s32 pid;
    __u32 reserved;
    __u64 addr;
    __u64 buffer;
    __u64 size;
};

struct vt_module_base {
    __s32 pid;
    __u32 reserved;
    __u64 name;
    __u64 base;
};

struct vt_hw_bp_info {
    __s32 pid;
    __u32 reserved0;
    __u64 addr;
    __s32 type;
    __s32 len;
    __u8 is_write_gp_regs;
    __u8 reserved1[3];
    __s32 gp_reg_count;
    __s32 gp_reg_indices[10];
    __u64 gp_reg_values[10];
    __u8 is_write_fp_regs;
    __u8 reserved2[3];
    __s32 fp_reg_count;
    __s32 fp_reg_indices[10];
    __u64 fp_reg_values[10][2];
};

struct vt_hwbp_hit_args {
    __s32 pid;
    __u32 reserved;
    __u64 addr;
    __u64 out_buf;
    __s32 out_len;
    __s32 real_count;
};

struct vt_tracking_data {
    __u8 is_active;
    __u8 reserved0[7];
    __u64 bp_addr;
    float x, y, z;
    __u32 reserved1;
};

#endif

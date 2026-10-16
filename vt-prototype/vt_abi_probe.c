/*
 * Interface probe for the recovered native AArch64 ABI.
 * This is a diagnostic subset, not a replacement VT driver.
 * Memory transfers are deliberately restricted to the calling process.
 */
#include <linux/module.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/sched.h>
#include <linux/capability.h>
#include <linux/compat.h>
#include <linux/build_bug.h>
#include <linux/errno.h>
#include "vt_protocol.h"

#define VT_PROBE_MAX_TRANSFER (64U * 1024U)

static long vt_transfer(unsigned int cmd, void __user *arg)
{
    struct vt_copy_memory request;
    void __user *src, *dst;
    void *scratch;
    long result = 0;

    if (copy_from_user(&request, arg, sizeof(request)))
        return -EFAULT;
    if (request.pid != task_tgid_vnr(current))
        return -EPERM;
    if (request.size > VT_PROBE_MAX_TRANSFER)
        return -E2BIG;
    if (!request.size)
        return 0;
    if (request.addr > ~0ULL - request.size ||
        request.buffer > ~0ULL - request.size)
        return -EFAULT;

    src = (void __user *)(unsigned long)(cmd == VT_MEMORY_READ ?
                                       request.addr : request.buffer);
    dst = (void __user *)(unsigned long)(cmd == VT_MEMORY_READ ?
                                       request.buffer : request.addr);
    scratch = kmalloc((size_t)request.size, GFP_KERNEL);
    if (!scratch)
        return -ENOMEM;
    if (copy_from_user(scratch, src, (size_t)request.size))
        result = -EFAULT;
    else if (copy_to_user(dst, scratch, (size_t)request.size))
        result = -EFAULT;
    kfree(scratch);
    return result;
}

static long vt_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    /* Check every request, including requests made through a passed descriptor. */
    if (!capable(CAP_SYS_RAWIO))
        return -EPERM;
    if (is_compat_task())
        return -EOPNOTSUPP;

    switch (cmd) {
    case VT_MEMORY_READ:
    case VT_MEMORY_WRITE:
        return vt_transfer(cmd, (void __user *)arg);
    case VT_HW_INSTALL:
    case VT_HW_HITS:
    case VT_HW_ENABLE:
    case VT_HW_CLEAR:
    case VT_HW_DISABLE:
    case VT_TRACKING:
    case VT_MODULE_BASE:
        return -EOPNOTSUPP;
    default:
        return -EINVAL;
    }
}

static const struct file_operations vt_fops = {
    .owner = THIS_MODULE,
    .unlocked_ioctl = vt_ioctl,
    .llseek = no_llseek,
};

static struct miscdevice vt_device = {
    .minor = MISC_DYNAMIC_MINOR,
    .name = "vt_abi_probe",
    .fops = &vt_fops,
    .mode = 0600,
};

static int __init vt_probe_init(void)
{
    BUILD_BUG_ON(sizeof(struct vt_copy_memory) != 32);
    BUILD_BUG_ON(sizeof(struct vt_module_base) != 24);
    BUILD_BUG_ON(sizeof(struct vt_hw_bp_info) != 360);
    BUILD_BUG_ON(sizeof(struct vt_hwbp_hit_args) != 32);
    BUILD_BUG_ON(sizeof(struct vt_tracking_data) != 32);
    pr_info("vt_abi_probe: diagnostic subset; self-process transfers only\n");
    return misc_register(&vt_device);
}

static void __exit vt_probe_exit(void)
{
    misc_deregister(&vt_device);
}

module_init(vt_probe_init);
module_exit(vt_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Recovered VT ABI diagnostic subset for ARM64");
MODULE_VERSION("0.1");

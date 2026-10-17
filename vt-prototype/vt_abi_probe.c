/*
 * Interface probe for the recovered native AArch64 ABI.
 * This is an incomplete replacement interface, not a complete VT driver.
 * Cross-process accesses go through procfs with the caller's credentials.
 */
#include <linux/module.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/sched.h>
#include <linux/capability.h>
#include <linux/compat.h>
#include <linux/bug.h>
#include <linux/errno.h>
#include <linux/string.h>
#include <linux/mm.h>
#include "vt_protocol.h"

#define VT_PROBE_MAX_TRANSFER (64U * 1024U)
#define VT_MAP_LINE 4096U
#define VT_MAP_LIMIT (4U * 1024U * 1024U)

static long vt_transfer(unsigned int cmd, void __user *arg)
{
    struct vt_copy_memory request;
    void __user *src, *dst;
    void *scratch;
    struct file *memory;
    char path[48];
    ssize_t transferred;
    long result = 0;

    if (copy_from_user(&request, arg, sizeof(request)))
        return -EFAULT;
    /* The unmodified client probes the read ABI with exactly this invalid
     * request. The original driver returns raw -1 (userspace EPERM), not
     * EINVAL. Keep it an error; no memory access or success is fabricated. */
    if (cmd == VT_MEMORY_READ && request.pid == -1 && !request.addr &&
        !request.buffer && !request.size)
        return -EPERM;
    if (request.pid <= 0)
        return -EINVAL;
    if (request.size > VT_PROBE_MAX_TRANSFER)
        return -E2BIG;
    if (!request.size)
        return 0;
    if (request.addr > ~0ULL - request.size ||
        request.buffer > ~0ULL - request.size)
        return -EFAULT;
    if (request.addr >= TASK_SIZE || request.size > TASK_SIZE - request.addr)
        return -EFAULT;

    src = (void __user *)(unsigned long)(cmd == VT_MEMORY_READ ?
                                       request.addr : request.buffer);
    dst = (void __user *)(unsigned long)(cmd == VT_MEMORY_READ ?
                                       request.buffer : request.addr);
    scratch = kmalloc((size_t)request.size, GFP_KERNEL);
    if (!scratch)
        return -ENOMEM;
    if (request.pid == task_tgid_vnr(current)) {
        if (copy_from_user(scratch, src, (size_t)request.size) ||
            copy_to_user(dst, scratch, (size_t)request.size))
            result = -EFAULT;
        goto free_scratch;
    }

    /* filp_open uses the caller's credentials: procfs performs its normal
     * ptrace/LSM access checks and pins the target mm for this descriptor. */
    snprintf(path, sizeof(path), "/proc/%d/mem", request.pid);
    memory = filp_open(path, cmd == VT_MEMORY_READ ? O_RDONLY : O_RDWR, 0);
    if (IS_ERR(memory)) {
        result = PTR_ERR(memory);
        goto free_scratch;
    }
    if (cmd == VT_MEMORY_READ) {
        transferred = kernel_read(memory, (loff_t)request.addr, scratch,
                                  (unsigned long)request.size);
        if (transferred == request.size) {
            if (copy_to_user(dst, scratch, (size_t)request.size))
                result = -EFAULT;
        } else {
            result = transferred < 0 ? transferred : -EIO;
        }
    } else if (copy_from_user(scratch, src, (size_t)request.size)) {
        result = -EFAULT;
    } else {
        transferred = kernel_write(memory, scratch, (size_t)request.size,
                                   (loff_t)request.addr);
        if (transferred != request.size)
            result = transferred < 0 ? transferred : -EIO;
    }
    filp_close(memory, NULL);
free_scratch:
    kfree(scratch);
    return result;
}

static bool vt_map_match(char *line, const char *wanted, unsigned long *base)
{
    char *p = line, *end, *basename;
    unsigned int field;
    unsigned long start = simple_strtoul(line, &end, 16);
    size_t length = strlen(wanted);

    if (end == line || *end != '-')
        return false;
    /* maps columns: range, permissions, offset, device, inode, path. */
    for (field = 0; field < 5; ++field) {
        while (*p == ' ' || *p == '\t')
            ++p;
        if (!*p)
            return false;
        while (*p && *p != ' ' && *p != '\t')
            ++p;
    }
    while (*p == ' ' || *p == '\t')
        ++p;
    if (*p != '/')
        return false;
    basename = strrchr(p, '/');
    p = wanted[0] == '/' ? p : basename + 1;
    if (strncmp(p, wanted, length))
        return false;
    if (p[length] && strcmp(p + length, " (deleted)"))
        return false;
    *base = start;
    return true;
}

static long vt_find_module(void __user *arg)
{
    struct vt_module_base request;
    struct file *maps;
    char path[48], chunk[512], *name, *line;
    unsigned long base = 0;
    unsigned int length = 0;
    loff_t position = 0;
    ssize_t count, i;
    long result = 0;

    if (copy_from_user(&request, arg, sizeof(request)))
        return -EFAULT;
    if (request.pid <= 0)
        return -EINVAL;
    name = strndup_user((const char __user *)(unsigned long)request.name, 256);
    if (IS_ERR(name))
        return PTR_ERR(name);
    if (!*name) {
        result = -EINVAL;
        goto free_name;
    }
    line = kmalloc(VT_MAP_LINE, GFP_KERNEL);
    if (!line) {
        result = -ENOMEM;
        goto free_name;
    }
    snprintf(path, sizeof(path), "/proc/%d/maps", request.pid);
    maps = filp_open(path, O_RDONLY, 0);
    if (IS_ERR(maps)) {
        result = PTR_ERR(maps);
        goto free_line;
    }
    for (;;) {
        count = kernel_read(maps, position, chunk, sizeof(chunk));
        if (count <= 0) {
            if (count < 0)
                result = count;
            break;
        }
        position += count;
        if (position > VT_MAP_LIMIT) {
            result = -E2BIG;
            break;
        }
        for (i = 0; i < count; ++i) {
            if (chunk[i] == '\n') {
                line[length] = 0;
                if (vt_map_match(line, name, &base))
                    goto found;
                length = 0;
            } else if (length < VT_MAP_LINE - 1) {
                line[length++] = chunk[i];
            } else {
                result = -ENAMETOOLONG;
                goto found;
            }
        }
    }
found:
    filp_close(maps, NULL);
    if (!result) {
        request.base = base;
        if (copy_to_user(arg, &request, sizeof(request)))
            result = -EFAULT;
    }
free_line:
    kfree(line);
free_name:
    kfree(name);
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
    case VT_MODULE_BASE:
        return vt_find_module((void __user *)arg);
    case VT_HW_INSTALL:
    case VT_HW_HITS:
    case VT_HW_ENABLE:
    case VT_HW_CLEAR:
    case VT_HW_DISABLE:
    case VT_TRACKING:
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

/* The client enumerates six-character alphanumeric character devices. */
static struct miscdevice vt_compat_device = {
    .minor = MISC_DYNAMIC_MINOR,
    .name = "VTp03A",
    .fops = &vt_fops,
    .mode = 0600,
};

static int __init vt_probe_init(void)
{
    int result;
    BUILD_BUG_ON(sizeof(struct vt_copy_memory) != 32);
    BUILD_BUG_ON(sizeof(struct vt_module_base) != 24);
    BUILD_BUG_ON(sizeof(struct vt_hw_bp_info) != 360);
    BUILD_BUG_ON(sizeof(struct vt_hwbp_hit_args) != 32);
    BUILD_BUG_ON(sizeof(struct vt_tracking_data) != 32);
    result = misc_register(&vt_device);
    if (result)
        return result;
    result = misc_register(&vt_compat_device);
    if (result) {
        misc_deregister(&vt_device);
        return result;
    }
    pr_info("vt_abi_probe: procfs-authorized access; discovery node VTp03A\n");
    return 0;
}

static void __exit vt_probe_exit(void)
{
    misc_deregister(&vt_compat_device);
    misc_deregister(&vt_device);
}

module_init(vt_probe_init);
module_exit(vt_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Recovered VT ABI diagnostic subset for ARM64");
MODULE_VERSION("0.3");

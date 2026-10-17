/*
 * Diagnostic subset of the recovered native AArch64 ABI, plus the module and
 * device hiding behaviour recovered from the original driver (module-7.ko).
 * This is an incomplete replacement interface, not a complete VT driver.
 * Cross-process accesses go through procfs with the caller's credentials.
 */
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/fs.h>
#include <linux/cdev.h>
#include <linux/device.h>
#include <linux/kobject.h>
#include <linux/list.h>
#include <linux/mutex.h>
#include <linux/random.h>
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

/* module-7.ko get_rand_str() picks six characters from this table. */
#define VT_NAME_LEN 6
static const char vt_name_charset[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

/* One character device owned by this module. */
struct vt_node {
    struct cdev cdev;
    struct class *class;
    dev_t dev;
    const char *name;
    unsigned int open_count;
    bool added;
    bool node_visible;
    struct mutex lock;
};

static struct lock_class_key vt_class_key;

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

static int vt_open(struct inode *inode, struct file *file);
static int vt_release(struct inode *inode, struct file *file);

static const struct file_operations vt_fops = {
    .owner = THIS_MODULE,
    .open = vt_open,
    .release = vt_release,
    .unlocked_ioctl = vt_ioctl,
    .llseek = no_llseek,
};

/* The original driver removes the /dev node as soon as a client opens it and
 * recreates the class and node when the last descriptor is closed. */
static void vt_node_unpublish(struct vt_node *node)
{
    if (!node->node_visible)
        return;
    device_destroy(node->class, node->dev);
    class_destroy(node->class);
    node->class = NULL;
    node->node_visible = false;
}

static void vt_node_publish(struct vt_node *node)
{
    struct device *device;

    if (node->node_visible || !node->name)
        return;
    node->class = __class_create(THIS_MODULE, node->name, &vt_class_key);
    if (IS_ERR(node->class)) {
        node->class = NULL;
        pr_warn("vt_abi_probe: cannot recreate %s class\n", node->name);
        return;
    }
    device = device_create(node->class, NULL, node->dev, NULL, "%s", node->name);
    if (IS_ERR(device)) {
        class_destroy(node->class);
        node->class = NULL;
        pr_warn("vt_abi_probe: cannot recreate /dev/%s\n", node->name);
        return;
    }
    node->node_visible = true;
}

static int vt_open(struct inode *inode, struct file *file)
{
    struct vt_node *node = container_of(inode->i_cdev, struct vt_node, cdev);

    file->private_data = node;
    mutex_lock(&node->lock);
    ++node->open_count;
    vt_node_unpublish(node);
    mutex_unlock(&node->lock);
    return 0;
}

static int vt_release(struct inode *inode, struct file *file)
{
    struct vt_node *node = file->private_data;

    if (!node)
        return 0;
    mutex_lock(&node->lock);
    if (node->open_count)
        --node->open_count;
    if (!node->open_count && node->added)
        vt_node_publish(node);
    mutex_unlock(&node->lock);
    return 0;
}

static int vt_node_add(struct vt_node *node, const char *name)
{
    struct device *device;
    int result;

    memset(node, 0, sizeof(*node));
    mutex_init(&node->lock);
    node->name = name;
    result = alloc_chrdev_region(&node->dev, 0, 1, name);
    if (result)
        return result;
    cdev_init(&node->cdev, &vt_fops);
    node->cdev.owner = THIS_MODULE;
    result = cdev_add(&node->cdev, node->dev, 1);
    if (result)
        goto drop_region;
    node->class = __class_create(THIS_MODULE, name, &vt_class_key);
    if (IS_ERR(node->class)) {
        result = PTR_ERR(node->class);
        node->class = NULL;
        goto drop_cdev;
    }
    device = device_create(node->class, NULL, node->dev, NULL, "%s", name);
    if (IS_ERR(device)) {
        result = PTR_ERR(device);
        class_destroy(node->class);
        node->class = NULL;
        goto drop_cdev;
    }
    node->node_visible = true;
    node->added = true;
    return 0;

drop_cdev:
    cdev_del(&node->cdev);
drop_region:
    unregister_chrdev_region(node->dev, 1);
    return result;
}

static void vt_node_remove(struct vt_node *node)
{
    if (!node->added)
        return;
    vt_node_unpublish(node);
    cdev_del(&node->cdev);
    unregister_chrdev_region(node->dev, 1);
    node->added = false;
}

/* module-7.ko get_rand_str(): one 32-bit random value per character. */
static void vt_random_name(char *out, unsigned int length)
{
    unsigned int i;
    int modulus = (int)(sizeof(vt_name_charset) - 1);

    for (i = 0; i < length; ++i) {
        unsigned int value;
        int index;

        get_random_bytes(&value, (int)sizeof(value));
        index = (int)value % modulus;
        if (index < 0)
            index = -index;
        out[i] = vt_name_charset[index];
    }
    out[length] = 0;
}

/* The original driver unlinks itself from the module list and drops its sysfs
 * kobject after the device is published, so neither /proc/modules nor
 * /sys/module/<name> lists it afterwards. */
static void vt_hide_module(void)
{
    list_del_init(&THIS_MODULE->list);
    kobject_del(&THIS_MODULE->mkobj.kobj);
}

static struct vt_node vt_discovery_node;
static struct vt_node vt_diag_node;
static char vt_discovery_name[VT_NAME_LEN + 1];

static bool hide_module = true;
module_param(hide_module, bool, 0400);
MODULE_PARM_DESC(hide_module,
    "Unlink the module from the kernel module list and sysfs like the original driver; load with hide_module=0 to keep rmmod usable");

static int __init vt_probe_init(void)
{
    int result;

    BUILD_BUG_ON(sizeof(struct vt_copy_memory) != 32);
    BUILD_BUG_ON(sizeof(struct vt_module_base) != 24);
    BUILD_BUG_ON(sizeof(struct vt_hw_bp_info) != 360);
    BUILD_BUG_ON(sizeof(struct vt_hwbp_hit_args) != 32);
    BUILD_BUG_ON(sizeof(struct vt_tracking_data) != 32);

    /* The client enumerates six-character alphanumeric character devices. */
    vt_random_name(vt_discovery_name, VT_NAME_LEN);
    result = vt_node_add(&vt_discovery_node, vt_discovery_name);
    if (result)
        return result;
    result = vt_node_add(&vt_diag_node, "vt_abi_probe");
    if (result) {
        vt_node_remove(&vt_discovery_node);
        return result;
    }
    pr_info("vt_abi_probe: discovery node /dev/%s, diagnostic node /dev/vt_abi_probe\n",
            vt_discovery_name);
    if (hide_module) {
        vt_hide_module();
        pr_info("vt_abi_probe: unlinked from the module list; rmmod needs a reboot\n");
    }
    return 0;
}

static void __exit vt_probe_exit(void)
{
    vt_node_remove(&vt_diag_node);
    vt_node_remove(&vt_discovery_node);
}

module_init(vt_probe_init);
module_exit(vt_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Recovered VT ABI diagnostic subset for ARM64");
MODULE_VERSION("0.4");

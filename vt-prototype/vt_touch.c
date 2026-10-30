// SPDX-License-Identifier: GPL-2.0-only
/* Visible, independently unloadable touchscreen companion for the VT project. */
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/input.h>
#include <linux/input/mt.h>
#include <linux/miscdevice.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/capability.h>
#include <linux/compat.h>
#include <linux/mutex.h>
#include <linux/delay.h>
#include "vt_touch_protocol.h"

static unsigned int width = 1080;
static unsigned int height = 2248;
module_param(width, uint, 0444);
module_param(height, uint, 0444);
MODULE_PARM_DESC(width, "Native portrait touch width in pixels (default 1080)");
MODULE_PARM_DESC(height, "Native portrait touch height in pixels (default 2248)");

static struct input_dev *vt_touch_input;
static DEFINE_MUTEX(vt_touch_lock);
static u64 completed_clicks;

static long vt_touch_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct vt_touch_click click;
    struct vt_touch_info info = { 0 };

    if (!capable(CAP_SYS_RAWIO))
        return -EPERM;
    if (is_compat_task())
        return -EOPNOTSUPP;

    switch (cmd) {
    case VT_TOUCH_GET_INFO:
        info.version = VT_TOUCH_ABI_VERSION;
        info.width = width;
        info.height = height;
        mutex_lock(&vt_touch_lock);
        info.completed_clicks = completed_clicks;
        mutex_unlock(&vt_touch_lock);
        return copy_to_user((void __user *)arg, &info, sizeof(info)) ? -EFAULT : 0;
    case VT_TOUCH_CLICK:
        if (copy_from_user(&click, (void __user *)arg, sizeof(click)))
            return -EFAULT;
        if (click.reserved || click.x >= width || click.y >= height ||
            click.duration_ms < VT_TOUCH_MIN_MS ||
            click.duration_ms > VT_TOUCH_MAX_MS)
            return -EINVAL;

        /* One full press/release per call. No persistent down state can be
         * abandoned if the caller exits. Serialize complete gestures. */
        mutex_lock(&vt_touch_lock);
        input_mt_slot(vt_touch_input, 0);
        input_mt_report_slot_state(vt_touch_input, MT_TOOL_FINGER, true);
        input_report_abs(vt_touch_input, ABS_MT_POSITION_X, click.x);
        input_report_abs(vt_touch_input, ABS_MT_POSITION_Y, click.y);
        input_mt_sync_frame(vt_touch_input);
        input_sync(vt_touch_input);
        msleep(click.duration_ms);
        input_mt_slot(vt_touch_input, 0);
        input_mt_report_slot_state(vt_touch_input, MT_TOOL_FINGER, false);
        input_mt_sync_frame(vt_touch_input);
        input_sync(vt_touch_input);
        ++completed_clicks;
        mutex_unlock(&vt_touch_lock);
        return 0;
    default:
        return -ENOTTY;
    }
}

static const struct file_operations vt_touch_fops = {
    .owner = THIS_MODULE,
    .unlocked_ioctl = vt_touch_ioctl,
    .llseek = no_llseek,
};

static struct miscdevice vt_touch_device = {
    .minor = MISC_DYNAMIC_MINOR,
    .name = "vt_touch",
    .fops = &vt_touch_fops,
    .mode = 0600,
};

static int __init vt_touch_init(void)
{
    int result;

    BUILD_BUG_ON(sizeof(struct vt_touch_info) != 24);
    BUILD_BUG_ON(sizeof(struct vt_touch_click) != 16);
    if (width < 16 || width > 16384 || height < 16 || height > 16384)
        return -EINVAL;
    vt_touch_input = input_allocate_device();
    if (!vt_touch_input)
        return -ENOMEM;
    vt_touch_input->name = "VT Touchscreen";
    vt_touch_input->phys = "vt_touch/input0";
    vt_touch_input->id.bustype = BUS_VIRTUAL;
    vt_touch_input->id.vendor = 0x5654;
    vt_touch_input->id.product = 1;
    vt_touch_input->id.version = 2;
    input_set_abs_params(vt_touch_input, ABS_MT_POSITION_X, 0, width - 1, 0, 0);
    input_set_abs_params(vt_touch_input, ABS_MT_POSITION_Y, 0, height - 1, 0, 0);
    /* Android ignores ABS_MT_SLOT when its range is 0..0 and falls back to
     * type A. Then unchanged axes suppressed by input core can be lost on
     * the next contact. Advertise two slots for real protocol B, use slot 0. */
    result = input_mt_init_slots(vt_touch_input, 2, INPUT_MT_DIRECT);
    if (result)
        goto free_input;
    result = input_register_device(vt_touch_input);
    if (result)
        goto free_input;
    result = misc_register(&vt_touch_device);
    if (result) {
        input_unregister_device(vt_touch_input);
        vt_touch_input = NULL;
        return result;
    }
    pr_info("vt_touch: /dev/vt_touch ready, native coordinates %ux%u\n", width, height);
    return 0;

free_input:
    input_free_device(vt_touch_input);
    vt_touch_input = NULL;
    return result;
}

static void __exit vt_touch_exit(void)
{
    misc_deregister(&vt_touch_device);
    input_unregister_device(vt_touch_input);
}

module_init(vt_touch_init);
module_exit(vt_touch_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Visible VT touchscreen click interface for dipper 4.9");
MODULE_VERSION("0.2");

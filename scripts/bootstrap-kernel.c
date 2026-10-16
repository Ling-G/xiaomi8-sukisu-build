/* Retain optional boot-owned resources across Android 10 SwitchRoot.
 * No user data or partition is accessed here. Missing payload is a no-op.
 * Included by the pinned 4.9 KSU unity build after kernel_compat.h.
 */
#include <linux/vmalloc.h>

struct dipper_boot_blob {
    const char *source;
    const char *destination;
    size_t limit;
    void *data;
    size_t size;
};

static struct dipper_boot_blob dipper_boot_blobs[] = {
    { "/dipper-ksud", "/dev/dipper-ksud", 6 * 1024 * 1024, NULL, 0 },
    { "/dipper-bootstrap.sh", "/dev/dipper-bootstrap.sh", 16 * 1024, NULL, 0 },
};

static void __init dipper_capture_bootstrap(void)
{
    unsigned int i;
    for (i = 0; i < ARRAY_SIZE(dipper_boot_blobs); i++) {
        struct dipper_boot_blob *blob = &dipper_boot_blobs[i];
        struct file *file;
        loff_t pos = 0;
        ssize_t count;
        loff_t size;
        file = filp_open(blob->source, O_RDONLY | O_NOFOLLOW, 0);
        if (IS_ERR(file))
            continue;
        size = i_size_read(file_inode(file));
        if (!S_ISREG(file_inode(file)->i_mode) || size <= 0 || size > blob->limit)
            goto close;
        blob->data = vmalloc(size);
        if (!blob->data)
            goto close;
        count = kernel_read(file, blob->data, size, &pos);
        if (count != size) {
            vfree(blob->data);
            blob->data = NULL;
        } else {
            blob->size = size;
            pr_info("dipper bootstrap: retained %s (%zu bytes)\n", blob->source, blob->size);
        }
close:
        filp_close(file, NULL);
    }
}

/* Called only from the existing PID 1 init.rc read hook, after /dev mounts. */
static void dipper_publish_bootstrap(void)
{
    unsigned int i;
    if (!dipper_boot_blobs[0].data || !dipper_boot_blobs[1].data)
        goto release;
    for (i = 0; i < ARRAY_SIZE(dipper_boot_blobs); i++) {
        struct dipper_boot_blob *blob = &dipper_boot_blobs[i];
        struct file *file;
        loff_t pos = 0;
        ssize_t count;
        file = filp_open(blob->destination, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0700);
        if (IS_ERR(file)) {
            pr_err("dipper bootstrap: publish %s failed: %ld\n", blob->destination, PTR_ERR(file));
            break;
        }
        count = kernel_write(file, blob->data, blob->size, &pos);
        filp_close(file, NULL);
        if (count != blob->size) {
            pr_err("dipper bootstrap: incomplete write to %s\n", blob->destination);
            break;
        }
        pr_info("dipper bootstrap: published %s\n", blob->destination);
    }
release:
    for (i = 0; i < ARRAY_SIZE(dipper_boot_blobs); i++) {
        vfree(dipper_boot_blobs[i].data);
        dipper_boot_blobs[i].data = NULL;
    }
}

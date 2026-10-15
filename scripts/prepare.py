#!/usr/bin/env python3
"""Apply checked MiCode dipper-q-oss / SukiSU builtin integration."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

PINS = {
    "kernel": "dcfb1676925aec83b06ae04fd8ca989ced75067c",
    "sukisu": "2d1de629d4204d25cc0c8927b959d9135d9781f4",
}

def replace_once(file, old, new):
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{file}: expected one patch location, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

def guard(declarations):
    return "#ifdef CONFIG_KSU\n" + declarations + "\n#endif\n\n"

def integrate(kernel, suki):
    target = kernel / "drivers/kernelsu"
    if target.exists():
        raise RuntimeError("Use a clean kernel checkout; drivers/kernelsu already exists")
    shutil.copytree(suki / "kernel", target)
    # Preserve the branch's version algorithm, but pin the compatibility version
    # to the selected manager release rather than querying mutable GitHub state.
    mf = target / "Makefile"
    text = mf.read_text(encoding="utf-8")
    a = text.index("REPO_OWNER  :=")
    b = text.index("KERNEL_VERSION :=", a)
    text = text[:a] + '''KSU_VERSION := 40900
KSU_VERSION_FULL := builtin-2d1de629-dipper-port
ccflags-y += -DKSU_VERSION=$(KSU_VERSION)
ccflags-y += -DKSU_VERSION_FULL=\\"$(KSU_VERSION_FULL)\\"
''' + text[b:]
    text = text.replace(" -Wno-gcc-compat", "").replace(" -Wno-int-conversion", "")
    mf.write_text(text, encoding="utf-8", newline="\n")
    inc = target / "kernel_includes.h"
    text = inc.read_text(encoding="utf-8")
    for name in ("limits.h", "input-event-codes.h"):
        if not (kernel / "include/linux" / name).exists():
            if not (kernel / "include/uapi/linux" / name).exists():
                raise RuntimeError(f"No compatible header for {name}")
            text = text.replace(f"<linux/{name}>", f"<uapi/linux/{name}>")
    inc.write_text(text, encoding="utf-8", newline="\n")
    with (kernel / "drivers/Makefile").open("a", encoding="utf-8", newline="\n") as f:
        f.write("\nobj-$(CONFIG_KSU) += kernelsu/\n")
    replace_once(kernel / "drivers/Kconfig", "endmenu", 'source "drivers/kernelsu/Kconfig"\n\nendmenu')

    file = kernel / "fs/exec.c"
    anchor = "static int do_execveat_common(int fd, struct filename *filename,"
    replace_once(file, anchor, guard("extern int ksu_handle_execveat(int *fd, struct filename **filename,\n"
        "    void *argv, void *envp, int *flags);") + anchor)
    old = "\tif (IS_ERR(filename))\n\t\treturn PTR_ERR(filename);\n\n\t/*\n\t * We move the actual failure"
    new = "\tif (IS_ERR(filename))\n\t\treturn PTR_ERR(filename);\n\n#ifdef CONFIG_KSU\n"
    new += "\tksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);\n#endif\n\n\t/*\n\t * We move the actual failure"
    replace_once(file, old, new)

    file = kernel / "fs/open.c"
    anchor = "SYSCALL_DEFINE3(faccessat, int, dfd, const char __user *, filename, int, mode)"
    replace_once(file, anchor, guard("extern int ksu_handle_faccessat(int *dfd, const char __user **filename,\n"
        "    int *mode, int *flags);") + anchor)
    anchor = "\tif (mode & ~S_IRWXO)\t/* where's F_OK, X_OK, W_OK, R_OK? */"
    replace_once(file, anchor, "#ifdef CONFIG_KSU\n\tksu_handle_faccessat(&dfd, &filename, &mode, NULL);\n#endif\n\n" + anchor)

    file = kernel / "fs/stat.c"
    anchor = "int vfs_fstat(unsigned int fd, struct kstat *stat)"
    replace_once(file, anchor, guard("extern void ksu_handle_vfs_fstat(int fd, loff_t *size);") + anchor)
    anchor = "\t\terror = vfs_getattr(&f.file->f_path, stat);\n\t\tfdput(f);"
    replace_once(file, anchor, "\t\terror = vfs_getattr(&f.file->f_path, stat);\n#ifdef CONFIG_KSU\n"
        "\t\tif (!error)\n\t\t\tksu_handle_vfs_fstat(fd, &stat->size);\n#endif\n\t\tfdput(f);")
    anchor = "int vfs_fstatat(int dfd, const char __user *filename, struct kstat *stat,"
    replace_once(file, anchor, guard("extern int ksu_handle_stat(int *dfd, const char __user **filename, int *flags);") + anchor)
    anchor = "\tif ((flag & ~(AT_SYMLINK_NOFOLLOW | AT_NO_AUTOMOUNT |"
    replace_once(file, anchor, "#ifdef CONFIG_KSU\n\tksu_handle_stat(&dfd, &filename, &flag);\n#endif\n\n" + anchor)

    file = kernel / "fs/read_write.c"
    anchor = "ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)"
    replace_once(file, anchor, guard("extern bool ksu_vfs_read_hook;\n"
        "extern int ksu_handle_vfs_read(struct file **file, char __user **buf,\n"
        "    size_t *count, loff_t **pos);") + anchor)
    # Scope to vfs_read: the same mode check also appears in vfs_readv.
    text = file.read_text(encoding="utf-8")
    start = text.index(anchor)
    prefix, body = text[:start], text[start:]
    marker = "\tif (!(file->f_mode & FMODE_READ))"
    if marker not in body:
        raise RuntimeError("vfs_read mode check missing")
    body = body.replace(marker, "#ifdef CONFIG_KSU\n\tif (unlikely(ksu_vfs_read_hook))\n"
        "\t\tksu_handle_vfs_read(&file, &buf, &count, &pos);\n#endif\n\n" + marker, 1)
    file.write_text(prefix + body, encoding="utf-8", newline="\n")

    file = kernel / "kernel/reboot.c"
    anchor = "SYSCALL_DEFINE4(reboot, int, magic1, int, magic2, unsigned int, cmd,"
    replace_once(file, anchor, guard("extern int ksu_handle_sys_reboot(int magic1, int magic2,\n"
        "    unsigned int cmd, void __user **arg);") + anchor)
    anchor = "\t/* We only trust the superuser with rebooting the system. */"
    replace_once(file, anchor, "#ifdef CONFIG_KSU\n"
        "\tif ((unsigned int)magic1 == 0xDEADBEEF &&\n"
        "\t    (unsigned int)magic2 == 0xCAFEBABE)\n"
        "\t\treturn ksu_handle_sys_reboot(magic1, magic2, cmd, &arg);\n"
        "#endif\n\n" + anchor)

    # Backport the consuming path_umount API using this kernel's own checks.
    file = kernel / "fs/namespace.c"
    anchor = "static inline bool may_mandlock(void)"
    wrapper = '''#ifdef CONFIG_KSU
int path_umount(struct path *path, int flags)
{
    struct mount *mnt = real_mount(path->mnt);
    int ret = -EINVAL;

    if (flags & ~(MNT_FORCE | MNT_DETACH | MNT_EXPIRE | UMOUNT_NOFOLLOW))
        goto out;
    ret = -EPERM;
    if (!may_mount())
        goto out;
    ret = -EINVAL;
    if (path->dentry != path->mnt->mnt_root || !check_mnt(mnt) ||
        (mnt->mnt.mnt_flags & MNT_LOCKED))
        goto out;
    ret = -EPERM;
    if ((flags & MNT_FORCE) && !capable(CAP_SYS_ADMIN))
        goto out;
    ret = do_umount(mnt, flags);
out:
    dput(path->dentry);
    mntput_no_expire(mnt);
    return ret;
}
#endif

'''
    replace_once(file, anchor, wrapper + anchor)

    # Port the compiler warning checker to Python 3 without changing its policy.
    wrapper = kernel / "scripts/gcc-wrapper.py"
    replacements = [
        ("#! /usr/bin/env python2", "#! /usr/bin/env python3"),
        ('print >> sys.stderr, "error, forbidden warning:", m.group(2)',
         'print("error, forbidden warning:", m.group(2), file=sys.stderr)'),
        ('subprocess.Popen(args, stderr=subprocess.PIPE)',
         'subprocess.Popen(args, stderr=subprocess.PIPE, universal_newlines=True)'),
        ('print >> sys.stderr, line,', 'print(line, end="", file=sys.stderr)'),
        ("print >> sys.stderr, args[0] + ':',e.strerror",
         "print(args[0] + ':', e.strerror, file=sys.stderr)"),
        ("print >> sys.stderr, 'Is your PATH set correctly?'",
         "print('Is your PATH set correctly?', file=sys.stderr)"),
        ("print >> sys.stderr, ' '.join(args), str(e)",
         "print(' '.join(args), str(e), file=sys.stderr)"),
    ]
    for before, after in replacements:
        replace_once(wrapper, before, after)

    # Collect all diagnostics before failing, retaining the warning gate.
    replace_once(wrapper, 'ofile = None', 'ofile = None\nforbidden_warning = False')
    replace_once(wrapper, '        sys.exit(1)',
                 '        global forbidden_warning\n        forbidden_warning = True')
    replace_once(wrapper, '        result = proc.wait()',
                 '        result = proc.wait()\n'
                 '        if forbidden_warning:\n'
                 '            if ofile and os.path.exists(ofile):\n'
                 '                os.remove(ofile)\n'
                 '            result = 1')

    # Minimal fixes for this builtin snapshot on pre-5.10 kernels.
    compat = target / "infra/kernel_compat.h"
    text = compat.read_text(encoding="utf-8")
    text += "\n#ifndef fallthrough\n#define fallthrough do { } while (0)\n#endif\n"
    compat.write_text(text, encoding="utf-8", newline="\n")
    replace_once(target / "policy/feature.c",
                 '    [KSU_FEATURE_SELINUX_HIDE] = "selinux_hide",',
                 '#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)\n'
                 '    [KSU_FEATURE_SELINUX_HIDE] = "selinux_hide",\n#endif')
    observer = target / "manager/pkg_observer.c"
    text = observer.read_text(encoding="utf-8")
    if text.count("track_throne(TRACK_THRONE_FORCE_SYNCHRONOUS)") != 2:
        raise RuntimeError("Unexpected package observer interface")
    # This branch's track_throne(bool prune_only) already runs synchronously;
    # false requests the full manager scan instead of pruning alone.
    text = text.replace("track_throne(TRACK_THRONE_FORCE_SYNCHRONOUS)", "track_throne(false)")
    observer.write_text(text, encoding="utf-8", newline="\n")
    replace_once(target / "supercall/dispatch.c",
                 'ksu_strncpy_from_user_nofault(mnt, cmd.arg, sizeof(mnt))',
                 'ksu_strncpy_from_user_nofault(mnt, (const void __user *)(unsigned long)cmd.arg, sizeof(mnt))')

    replace_once(target / "supercall/dispatch.c",
                 'struct ksu_get_full_version_cmd cmd = { 0 };',
                 'struct ksu_get_full_version_cmd cmd = { .version_full = { 0 } };')

    replace_once(target / "supercall/dispatch.c",
                 'struct ksu_hook_type_cmd cmd = { 0 };',
                 'struct ksu_hook_type_cmd cmd = { .hook_type = { 0 } };')
    runtime = target / "runtime/ksud.c"
    text = runtime.read_text(encoding="utf-8")
    for call, expected_count in (('ksu_selinux_hide_handle_post_fs_data();', 1),
                                 ('ksu_selinux_hide_handle_second_stage();', 2)):
        if text.count(call) != expected_count:
            raise RuntimeError("Unexpected SELinux hide call sites")
        text = text.replace(call,
                            '#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)\n'
                            + call + '\n#endif')
    # Discover the already installed manager at boot, even when packages.list
    # has not changed. Signature verification stays in search_manager().
    if text.count("track_throne(true);") != 1:
        raise RuntimeError("Unexpected boot manager scan interface")
    text = text.replace("track_throne(true);", "track_throne(false);")
    if text.count("    ksu_observer_init();") != 1:
        raise RuntimeError("Unexpected post-fs-data observer initialization")
    text = text.replace("    ksu_observer_init();",
                        "    ksu_observer_init();\n    track_throne(false);")
    runtime.write_text(text, encoding="utf-8", newline="\n")
    replace_once(target / "sulog/event.c",
                 '#define USER_ARG_NULL user_arg_null_ptr()',
                 '#ifdef CONFIG_KSU_SUSFS\n'
                 '    #define USER_ARG_NULL user_arg_null_ptr()\n'
                 '#else\n'
                 '    #define USER_ARG_NULL (*user_arg_null_ptr())\n'
                 '#endif')
    replace_once(target / "selinux/rules.c",
                 'void apply_kernelsu_rules(void)\n{\n    struct selinux_policy *pol, *old_pol;',
                 'void apply_kernelsu_rules(void)\n{\n'
                 '#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 10, 0)\n'
                 '    struct selinux_policy *pol, *old_pol;\n#endif')

    # Report exact source integration, independently of version display strings.
    report = {"pins": PINS, "target": "dipper / MIUI 12.5.2 Android 10",
              "manager": "SukiSU v4.2.0 40900 (UAPI 2; runtime unverified)",
              "features": {"sukisu": True, "kpm": False, "susfs": False},
              "status": "source integrated; boot and root testing required"}
    (kernel / "integration.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("kernel", type=Path)
    p.add_argument("sukisu", type=Path)
    args = p.parse_args()
    integrate(args.kernel.resolve(), args.sukisu.resolve())
    print("SukiSU builtin integration applied")

#!/usr/bin/env python3
"""Apply the pinned SUSFS 2.3.0 Linux 4.9 port after the existing dipper fixes.
Upstream port: https://github.com/wxx9248/susfs4ksu
SUSFS upstream: https://gitlab.com/simonpunk/susfs4ksu
The derived patch and copied upstream files retain their GPL-2.0 license.
"""
import argparse,json,shutil,subprocess
from pathlib import Path

def replace(p,a,b):
 s=p.read_text();assert s.count(a)==1,(str(p),s.count(a));p.write_text(s.replace(a,b,1))

def prepare(k,s):
 patch=Path(__file__).parent/'patches/susfs-4.9-dipper.patch'
 subprocess.run(['git','apply','--check',str(patch.resolve())],cwd=k,check=True)
 subprocess.run(['git','apply',str(patch.resolve())],cwd=k,check=True)
 for n in ['fs/susfs.c','include/linux/susfs.h','include/linux/susfs_def.h']:
  shutil.copyfile(s/'kernel_patches'/n,k/n)
 replace(k/'include/linux/susfs_def.h','<linux/bits.h>','<linux/bitops.h>')
 # readlink(2) returns bytes copied. Preserve that ABI on a redirect hit.
 p=k/'fs/susfs.c';t=p.read_text();a=t.index('int susfs_open_redirect_spoof_vfs_readlink(');b=t.index('int susfs_open_redirect_spoof_do_proc_readlink(',a)
 body=t[a:b];assert body.count('\t\t\treturn 0;')==1
 body=body.replace('int srcu_idx =', 'int copied;\n\tint srcu_idx =', 1)
 body=body.replace('\t\t\tsrcu_read_unlock(&susfs_srcu_open_redirect, srcu_idx);\n\t\t\treturn 0;', '\t\t\tcopied = strlen(entry->info.redirected_pathname);\n\t\t\tsrcu_read_unlock(&susfs_srcu_open_redirect, srcu_idx);\n\t\t\treturn copied;', 1)
 p.write_text(t[:a]+body+t[b:])
 replace(k/'fs/namei.c','res = susfs_open_redirect_spoof_vfs_readlink(inode, buffer, buflen);\n\t\tif (!res)', 'res = susfs_open_redirect_spoof_vfs_readlink(inode, buffer, buflen);\n\t\tif (res >= 0)')
 replace(k/'drivers/kernelsu/Makefile','KSU_VERSION_FULL := builtin-2d1de629-dipper-port','KSU_VERSION_FULL := builtin-2d1de629-dipper-port-susfs2.3.0')
 # The SUSFS-only logging branch needs the same 4.9 compatibility wrappers.
 p=k/'drivers/kernelsu/sulog/event.c';t=p.read_text();a=t.index('static __u32 ksu_sulog_copy_filename_kernel(');b=t.index('static __u32 ksu_sulog_flatten_argv(',a)
 t=t[:a]+'''static __u32 ksu_sulog_copy_filename_kernel(const char *filename, char *dst, __u32 dst_len)
{
    size_t len;
    if (!dst_len)
        return 0;
    if (!filename)
        return ksu_sulog_copy_empty_string(dst);
    len = strnlen(filename, dst_len - 1);
    memcpy(dst, filename, len);
    dst[len] = '\\0';
    return len + 1;
}

'''+t[b:]
 assert t.count('            strncpy_from_user_nofault(')==1
 t=t.replace('            strncpy_from_user_nofault(', '            ksu_strncpy_from_user_nofault(');p.write_text(t)
 p=k/'drivers/kernelsu/selinux/selinux.c';t=p.read_text();a=t.index('#ifdef CONFIG_KSU_SUSFS\n#define KERNEL_INIT_DOMAIN');prefix,body=t[:a],t[a:]
 assert body.count('current_sid()')==5
 body=body.replace('current_sid()', 'ksu_susfs_current_sid_compat()')
 helper='''#ifdef CONFIG_KSU_SUSFS
static inline u32 ksu_susfs_current_sid_compat(void)
{
    const struct task_security_struct *tsec = selinux_cred(current_cred());
    return tsec ? tsec->sid : 0;
}
'''
 body=body.replace('#ifdef CONFIG_KSU_SUSFS',helper,1);p.write_text(prefix+body)
 p=k/'integration.json';r=json.loads(p.read_text());r['features']['susfs']=True;r['susfs']={'repository':'https://github.com/wxx9248/susfs4ksu','ref':'71345ded5af28f55d76ebcdc7a9df9cea56111e1','version':'v2.3.0','patch':'scripts/patches/susfs-4.9-dipper.patch','status':'experimental; runtime validation pending'};p.write_text(json.dumps(r,indent=2)+'\n')
 print('SUSFS v2.3.0 dipper source integration applied')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('kernel',type=Path);p.add_argument('susfs',type=Path);a=p.parse_args();prepare(a.kernel.resolve(),a.susfs.resolve())

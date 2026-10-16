#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
python3 - "$ROOT/scripts/build.sh" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]);s=p.read_text()
a='fetch_tree https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git "$KERNEL_REF" "$WORK/kernel"\n'
assert s.count(a)==1;s=s.replace(a,a+'fetch_tree https://github.com/wxx9248/susfs4ksu.git 71345ded5af28f55d76ebcdc7a9df9cea56111e1 "$WORK/susfs"\n',1)
a='python3 "$ROOT/scripts/prepare.py" "$WORK/kernel" "$WORK/sukisu"\n'
assert s.count(a)==1;s=s.replace(a,a+'python3 "$ROOT/scripts/prepare-susfs.py" "$WORK/kernel" "$WORK/susfs"\n',1)
opts=['KSU_SUSFS','KSU_SUSFS_SUS_PATH','KSU_SUSFS_SUS_MOUNT','KSU_SUSFS_SUS_KSTAT','KSU_SUSFS_SPOOF_UNAME','KSU_SUSFS_ENABLE_LOG','KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS','KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG','KSU_SUSFS_OPEN_REDIRECT','KSU_SUSFS_SUS_MAP']
a='--disable KSU_SUSFS';assert s.count(a)==1;s=s.replace(a,' '.join('--enable '+o for o in opts))
s=s.replace("grep -qx '# CONFIG_KSU_SUSFS is not set'", "grep -qx 'CONFIG_KSU_SUSFS=y'")
p.write_text(s)
PY
bash "$ROOT/scripts/build-builtin.sh"
"$ROOT/work/gcc64/bin/aarch64-linux-android-gcc" -Os -fno-builtin -fno-stack-protector -nostdlib -static -Wl,--build-id=none -Wl,-e,_start "$ROOT/scripts/susfs-query.c" -o "$ROOT/artifacts/susfs-query"
python3 - "$ROOT" <<'PY'
import json,sys,re,hashlib
from pathlib import Path
r=Path(sys.argv[1]);a=r/'artifacts';c=(a/'kernel.config').read_text();m=(a/'System.map').read_text()
opts=['KSU_SUSFS','KSU_SUSFS_SUS_PATH','KSU_SUSFS_SUS_MOUNT','KSU_SUSFS_SUS_KSTAT','KSU_SUSFS_SPOOF_UNAME','KSU_SUSFS_ENABLE_LOG','KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS','KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG','KSU_SUSFS_OPEN_REDIRECT','KSU_SUSFS_SUS_MAP']
for o in opts:assert re.search('^CONFIG_'+o+'=y$',c,re.M),o
symbols=['susfs_init','susfs_add_sus_path','susfs_set_uname','susfs_show_version','susfs_set_hide_sus_mnts_for_non_su_procs','ksu_handle_setresuid','ksu_handle_sys_reboot']
for n in symbols:assert re.search(r'\b'+n+r'$',m,re.M),n
(a/'susfs-check.json').write_text(json.dumps({'version':'v2.3.0','ref':'71345ded5af28f55d76ebcdc7a9df9cea56111e1','enabled_config':opts,'required_symbols':symbols,'passed':True,'hardware_validation':'pending'},indent=2)+'\n')
(a/'SUSFS-SHA256SUMS').write_text(''.join(hashlib.sha256((a/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in ['Image.gz','kernel.config','System.map','integration.json','susfs-check.json','susfs-query']))
PY

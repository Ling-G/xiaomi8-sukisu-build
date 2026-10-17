#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
export BOARD_PLATFORM=sdm845
python3 - "$ROOT/scripts/build.sh" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]);s=p.read_text()
a='fetch_tree https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git "$KERNEL_REF" "$WORK/kernel"\n'
b='fetch_tree https://github.com/MiCode/vendor_qcom_opensource_audio-kernel.git 27531fc846efac18206c65e0c09ad36cce514c76 "$WORK/kernel/techpack/audio"\n'
b+='fetch_tree https://github.com/MiCode/vendor_qcom_opensource_wlan.git e9c485b6ff4282c649ea4cff5116a613b0678cb4 "$WORK/wlan-builtin"\n'
b+='printf \'obj-y += audio/\\n\' > "$WORK/kernel/techpack/Makefile"\n'
assert s.count(a)==1;s=s.replace(a,a+b,1)
a='python3 "$ROOT/scripts/prepare.py" "$WORK/kernel" "$WORK/sukisu"\n'
assert s.count(a)==1;s=s.replace(a,a+'python3 "$ROOT/scripts/prepare-builtin.py" "$WORK/kernel" "$WORK/wlan-builtin"\n',1)
a='make O="$OUT" HOSTCFLAGS=\'-O2 -fcommon\' olddefconfig\n'
assert s.count(a)==1;s=s.replace(a,'scripts/config --file "$OUT/.config" --enable STAGING --enable QCA_CLD_WLAN\n'+a+'grep -qx CONFIG_QCA_CLD_WLAN=y "$OUT/.config"\n',1)
p.write_text(s)
PY
bash "$ROOT/scripts/build.sh"
python3 - "$ROOT" <<'PY'
import sys,re,json,hashlib
from pathlib import Path
r=Path(sys.argv[1]);a=r/'artifacts';out=r/'out';k=r/'work/kernel'
s=(a/'System.map').read_text()
required=['__initcall_hdd_module_init6','__initcall_wcd9xxx_core_init6','__initcall_wcd9xxx_soc_init6','__initcall_wsa881x_codec_init6','__initcall_swrm_init4','__initcall_wcd_pinctrl_driver_init6','__initcall_wdsp_glink_driver_init6','__initcall_wcd_spi_driver_init6','__initcall_tavil_codec_driver_init6','__initcall_sdm845_asoc_machine_driver_init6']
missing=[n for n in required if not re.search(r'\b'+n+r'$',s,re.M)]
assert not missing,missing
assert re.search(r'^CONFIG_QCA_CLD_WLAN=y$',(a/'kernel.config').read_text(),re.M)
conf=(k/'techpack/audio/config/sdm845auto.conf').read_text();assert '=m' not in conf
(a/'audio-builtin.conf').write_text(conf)
(a/'builtin-integration.json').write_bytes((k/'builtin-integration.json').read_bytes())
mods=sorted(set(line for p in out.rglob('modules.builtin') for line in p.read_text().splitlines()))
(a/'all-modules.builtin').write_text('\n'.join(mods)+'\n')
(a/'builtin-check.json').write_text(json.dumps({'passed':True,'required_builtin_initcalls':required,'audio_config':'all 13 former module options set to y','wifi_config':'CONFIG_QCA_CLD_WLAN=y','autoload_module_required':False,'hardware_validation':'pending'},indent=2)+'\n')
names=['Image.gz','kernel.config','System.map','audio-builtin.conf','builtin-integration.json','builtin-check.json','all-modules.builtin']
(a/'BUILTIN-SHA256SUMS').write_text(''.join(hashlib.sha256((a/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names))
PY

#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
# The Qualcomm audio core is a separately published MiCode source tree.
python3 - "$ROOT/scripts/build.sh" <<'PY'
import sys
from pathlib import Path
p=Path(sys.argv[1]);s=p.read_text()
anchor='fetch_tree https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git "$KERNEL_REF" "$WORK/kernel"\n'
assert s.count(anchor)==1
addition='fetch_tree https://github.com/MiCode/vendor_qcom_opensource_audio-kernel.git 27531fc846efac18206c65e0c09ad36cce514c76 "$WORK/kernel/techpack/audio"\n'
addition+='printf \'obj-y += audio/\\n\' > "$WORK/kernel/techpack/Makefile"\n'
p.write_text(s.replace(anchor,anchor+addition,1))
PY
bash "$ROOT/scripts/build-wifi.sh"
exec > >(tee "$ROOT/audio-build.log") 2>&1
WORK="$ROOT/work"
OUT="$ROOT/out"
ART="$ROOT/artifacts"
export ARCH=arm64 SUBARCH=arm64 LOCALVERSION=
export CROSS_COMPILE="$WORK/gcc64/bin/aarch64-linux-android-"
export CROSS_COMPILE_ARM32="$WORK/gcc32/bin/arm-linux-androideabi-"
export KBUILD_BUILD_USER=dipper-builder KBUILD_BUILD_HOST=github-actions
export KBUILD_BUILD_TIMESTAMP='Thu Oct 15 08:00:00 UTC 2026'
cd "$WORK/kernel"
make O="$OUT" HOSTCFLAGS='-O2 -fcommon' -j"$(nproc)" M=techpack/audio modules
mkdir -p "$ART/vendor-modules"
find "$OUT/techpack/audio" -type f -name '*.ko' -exec cp -t "$ART/vendor-modules" {} +
test -f "$ART/vendor-modules/snd-soc-sdm845.ko"
test -f "$ART/vendor-modules/wcd-core.ko"
cp "$ART/wifi-module/qca_cld3_wlan.ko" "$ART/vendor-modules/"
find "$ART/vendor-modules" -type f -name '*.ko' -exec "$CROSS_COMPILE"strip --strip-debug {} +
python3 "$ROOT/scripts/check_modules.py" "$ART/Image.gz" "$ART/System.map" "$ART/vendor-modules" --output "$ART/audio-wifi-abi-check.json"
cp "$OUT/techpack/audio/Module.symvers" "$ART/audio-Module.symvers"
# Retain one compact Wi-Fi module copy and refresh its checksum after stripping.
cp "$ART/vendor-modules/qca_cld3_wlan.ko" "$ART/wifi-module/qca_cld3_wlan.ko"
(cd "$ART" && sha256sum Image.gz wifi-module/qca_cld3_wlan.ko Module.symvers wifi-abi-check.json > WIFI-SHA256SUMS)
python3 - "$ART" <<'PY'
import sys,hashlib,json
from pathlib import Path
p=Path(sys.argv[1]);names=['Image.gz','System.map','audio-wifi-abi-check.json','audio-Module.symvers']
names += [f.relative_to(p).as_posix() for f in sorted((p/'vendor-modules').glob('*.ko'))]
(p/'AUDIO-SHA256SUMS').write_text(''.join(hashlib.sha256((p/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in names))
(p/'audio-source.json').write_text(json.dumps({'repository':'https://github.com/MiCode/vendor_qcom_opensource_audio-kernel','ref':'27531fc846efac18206c65e0c09ad36cce514c76','branch':'dipper-q-oss'},indent=2)+'\n')
PY

#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
bash "$ROOT/scripts/build.sh"
exec > >(tee "$ROOT/wifi-build.log") 2>&1
WORK="$ROOT/work"
OUT="$ROOT/out"
ART="$ROOT/artifacts"
git init -q "$WORK/wlan"
git -C "$WORK/wlan" remote add origin https://github.com/MiCode/vendor_qcom_opensource_wlan.git
git -C "$WORK/wlan" fetch --depth=1 origin e9c485b6ff4282c649ea4cff5116a613b0678cb4
git -C "$WORK/wlan" checkout -q --detach FETCH_HEAD
test "$(git -C "$WORK/wlan" rev-parse HEAD)" = e9c485b6ff4282c649ea4cff5116a613b0678cb4
export ARCH=arm64 SUBARCH=arm64 LOCALVERSION=
export CROSS_COMPILE="$WORK/gcc64/bin/aarch64-linux-android-"
export CROSS_COMPILE_ARM32="$WORK/gcc32/bin/arm-linux-androideabi-"
export KBUILD_BUILD_USER=dipper-builder KBUILD_BUILD_HOST=github-actions
export KBUILD_BUILD_TIMESTAMP='Thu Oct 15 08:00:00 UTC 2026'
cd "$WORK/kernel"
test -s "$OUT/Module.symvers"
make O="$OUT" HOSTCFLAGS='-O2 -fcommon' -j"$(nproc)" \
    M="$WORK/wlan/qcacld-3.0" WLAN_ROOT="$WORK/wlan/qcacld-3.0" \
    WLAN_COMMON_ROOT=../qca-wifi-host-cmn WLAN_COMMON_INC="$WORK/wlan/qca-wifi-host-cmn" \
    CONFIG_QCA_CLD_WLAN=m MODNAME=wlan BOARD_PLATFORM=sdm845 modules
mkdir -p "$ART/wifi-module"
cp "$WORK/wlan/qcacld-3.0/wlan.ko" "$ART/wifi-module/qca_cld3_wlan.ko"
cp "$OUT/Module.symvers" "$ART/Module.symvers"
python3 "$ROOT/scripts/check_modules.py" "$ART/Image.gz" "$ART/System.map" "$ART/wifi-module" --output "$ART/wifi-abi-check.json"
(cd "$ART" && sha256sum Image.gz wifi-module/qca_cld3_wlan.ko Module.symvers wifi-abi-check.json > WIFI-SHA256SUMS)

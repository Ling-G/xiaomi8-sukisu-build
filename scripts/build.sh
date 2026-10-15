#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
WORK="$ROOT/work"
OUT="$ROOT/out"
ART="$ROOT/artifacts"
mkdir -p "$WORK" "$OUT" "$ART"
exec > >(tee "$ROOT/build.log") 2>&1
fetch_tree() {
    local repo=$1 ref=$2 dest=$3
    if [[ -e "$dest" ]]; then
        echo "Expected clean destination: $dest" >&2
        return 1
    fi
    git init -q "$dest"
    git -C "$dest" remote add origin "$repo"
    git -C "$dest" fetch --depth=1 origin "$ref"
    git -C "$dest" checkout -q --detach FETCH_HEAD
    test "$(git -C "$dest" rev-parse HEAD)" = "$ref"
}
KERNEL_REF=dcfb1676925aec83b06ae04fd8ca989ced75067c
SUKISU_REF=2d1de629d4204d25cc0c8927b959d9135d9781f4
fetch_tree https://github.com/MiCode/Xiaomi_Kernel_OpenSource.git "$KERNEL_REF" "$WORK/kernel"
fetch_tree https://github.com/SukiSU-Ultra/SukiSU-Ultra.git "$SUKISU_REF" "$WORK/sukisu"
fetch_tree https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9 84fb09fafc92a3d9b4d160f049d46c3c784cc941 "$WORK/gcc64"
fetch_tree https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/arm/arm-linux-androideabi-4.9 5a8beef7b1aa2c8ca0dfe4a00358559d12dfa3b6 "$WORK/gcc32"
python3 "$ROOT/scripts/prepare.py" "$WORK/kernel" "$WORK/sukisu"
cp "$ROOT/stock/stock.config" "$OUT/.config"
cd "$WORK/kernel"
scripts/config --file "$OUT/.config" --enable KSU --disable KPM --disable KSU_SUSFS --disable KSU_DEBUG --disable KSU_FEATURE_ADBROOT --disable LOCALVERSION_AUTO --set-str LOCALVERSION '-perf-g10af704'
export ARCH=arm64 SUBARCH=arm64 LOCALVERSION=
export CROSS_COMPILE="$WORK/gcc64/bin/aarch64-linux-android-"
export CROSS_COMPILE_ARM32="$WORK/gcc32/bin/arm-linux-androideabi-"
export KBUILD_BUILD_USER=dipper-builder KBUILD_BUILD_HOST=github-actions
export KBUILD_BUILD_TIMESTAMP='Thu Oct 15 08:00:00 UTC 2026'
"$CROSS_COMPILE"gcc --version
make O="$OUT" HOSTCFLAGS='-O2 -fcommon' olddefconfig
grep -qx 'CONFIG_KSU=y' "$OUT/.config"
grep -qx '# CONFIG_KPM is not set' "$OUT/.config"
grep -qx '# CONFIG_KSU_SUSFS is not set' "$OUT/.config"
make O="$OUT" HOSTCFLAGS='-O2 -fcommon' -j"$(nproc)" prepare scripts
make O="$OUT" HOSTCFLAGS='-O2 -fcommon' init/version.o
make O="$OUT" HOSTCFLAGS='-O2 -fcommon' -j"$(nproc)" security/selinux/
# Check the integration object first so compatibility errors fail quickly.
make O="$OUT" HOSTCFLAGS='-O2 -fcommon' drivers/kernelsu/ksu.o
make O="$OUT" HOSTCFLAGS='-O2 -fcommon' -j"$(nproc)" Image.gz
cp "$OUT/arch/arm64/boot/Image.gz" "$ART/Image.gz"
cp "$OUT/.config" "$ART/kernel.config"
cp "$OUT/System.map" "$ART/System.map"
cp "$WORK/kernel/integration.json" "$ART/integration.json"
cp "$ROOT/pins.json" "$ART/pins.json"
make -s O="$OUT" kernelrelease > "$ART/kernelrelease.txt"
printf '%s\n' 'Experimental kernel: compilation success does not imply boot/root validation.' > "$ART/READ-BEFORE-USE.txt"
(cd "$ART" && sha256sum Image.gz kernel.config System.map integration.json pins.json > SHA256SUMS)

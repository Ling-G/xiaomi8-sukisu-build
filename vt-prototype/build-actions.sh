#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
export BOARD_PLATFORM=sdm845
python3 "$ROOT/vt-prototype/verify_abi.py"
bash "$ROOT/scripts/build-susfs.sh"
cd "$ROOT"
printf '%s  %s\n' cc904ba698d456659efb8eb85082e475c7e29142a4cf81dea3011d5b697faa9a artifacts/kernel.config | sha256sum -c -
test "$(cat artifacts/kernelrelease.txt)" = '4.9.186-perf-g10af704'
make -C vt-prototype KDIR="$ROOT/out" ARCH=arm64 \
    CROSS_COMPILE="$ROOT/work/gcc64/bin/aarch64-linux-android-" HOSTCFLAGS='-O2 -fcommon'
mkdir -p vt-probe-artifacts
cp vt-prototype/vt_abi_probe.ko vt-probe-artifacts/
python3 vt-prototype/verify_module.py vt-probe-artifacts/vt_abi_probe.ko artifacts/Module.symvers vt-probe-artifacts/module-check.json
python3 - "$ROOT" <<'PY'
from pathlib import Path
import json,sys
r=Path(sys.argv[1])
report=json.loads((r/'vt-probe-artifacts/module-check.json').read_text())
expected=json.loads((r/'vt-prototype/expected-crcs.json').read_text())
for name,crc in report['checked_symbol_crcs'].items():
    assert name in expected['symbols'], ('missing provided-table CRC',name)
    assert int(crc,16)==int(expected['symbols'][name],16), ('provided-table CRC mismatch',name)
report['provided_symvers_sha256']=expected['provided_symvers_sha256']
report['provided_table_import_crcs_match']=True
(r/'vt-probe-artifacts/module-check.json').write_text(json.dumps(report,indent=2)+'\n')
PY
"$ROOT/work/gcc64/bin/aarch64-linux-android-gcc" -Os -ffreestanding -fno-builtin -fno-stack-protector \
    -nostdlib -static -Wl,--build-id=none -Wl,-e,_start vt-prototype/probe_client.c -o vt-probe-artifacts/vt_probe_test
cp artifacts/kernel.config artifacts/Module.symvers artifacts/kernelrelease.txt artifacts/symvers-check.json vt-probe-artifacts/
cp vt-prototype/README.md vt-probe-artifacts/README-source-status.md
git rev-parse HEAD > vt-probe-artifacts/source-commit.txt
(cd vt-probe-artifacts && sha256sum vt_abi_probe.ko vt_probe_test Module.symvers kernel.config module-check.json > SHA256SUMS)

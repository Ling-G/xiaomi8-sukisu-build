#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
export BOARD_PLATFORM=sdm845
python3 "$ROOT/vt-prototype/verify_abi.py"
# Compose the existing pinned integration recipe, but stop after preparing
# the matching headers and host tools. Authoritative symbol CRCs are supplied.
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
r=Path(sys.argv[1])
p=r/'scripts/build.sh'
s=p.read_text()
anchor='# Reject missing module CRCs before producing another test image.'
assert s.count(anchor)==1
s=s.replace(anchor,'''cp "$OUT/.config" "$ART/kernel.config"
make -s O="$OUT" kernelrelease > "$ART/kernelrelease.txt"
exit 0
'''+anchor,1)
p.write_text(s)
p=r/'scripts/build-builtin.sh';s=p.read_text()
anchor='bash "$ROOT/scripts/build.sh"\n'
assert s.count(anchor)==1
p.write_text(s.split(anchor,1)[0]+anchor)
p=r/'scripts/build-susfs.sh';s=p.read_text()
anchor='bash "$ROOT/scripts/build-builtin.sh"\n'
assert s.count(anchor)==1
p.write_text(s.split(anchor,1)[0]+anchor)
PY
bash "$ROOT/scripts/build-susfs.sh"
cd "$ROOT"
printf '%s  %s\n' cc904ba698d456659efb8eb85082e475c7e29142a4cf81dea3011d5b697faa9a artifacts/kernel.config | sha256sum -c -
test "$(cat artifacts/kernelrelease.txt)" = '4.9.186-perf-g10af704'
python3 - "$ROOT" <<'PY'
from pathlib import Path
import json,sys
r=Path(sys.argv[1]);expected=json.loads((r/'vt-prototype/expected-crcs.json').read_text())
lines=[]
for name,crc in expected['symbols'].items():
    lines.append(f"{crc}\t{name}\tvmlinux\t{expected['export_types'][name]}\n")
(r/'out/Module.symvers').write_text(''.join(lines))
PY
make -C vt-prototype KDIR="$ROOT/out" ARCH=arm64 \
    CROSS_COMPILE="$ROOT/work/gcc64/bin/aarch64-linux-android-" HOSTCFLAGS='-O2 -fcommon'
mkdir -p vt-probe-artifacts
cp vt-prototype/vt_abi_probe.ko vt-probe-artifacts/
python3 vt-prototype/verify_module.py vt-probe-artifacts/vt_abi_probe.ko out/Module.symvers vt-probe-artifacts/module-check.json
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
report['symvers_scope']='Subset of provided table sufficient for diagnostic module imports; not the complete kernel export table'
(r/'vt-probe-artifacts/module-check.json').write_text(json.dumps(report,indent=2)+'\n')
PY
"$ROOT/work/gcc64/bin/aarch64-linux-android-gcc" -Os -ffreestanding -fno-builtin -fno-stack-protector \
    -nostdlib -static -Wl,--build-id=none -Wl,-e,_start vt-prototype/probe_client.c -o vt-probe-artifacts/vt_probe_test
"$ROOT/work/gcc64/bin/aarch64-linux-android-gcc" -Os -fPIC -shared -ffreestanding -fno-builtin -fno-stack-protector \
    -nostdlib -DVT_DISCOVERY_TRACE vt-prototype/probe_client.c -o vt-probe-artifacts/vt_discovery_trace.so
cp artifacts/kernel.config artifacts/kernelrelease.txt vt-probe-artifacts/
cp out/Module.symvers vt-probe-artifacts/Module.symvers
cp vt-prototype/README.md vt-probe-artifacts/README-source-status.md
git rev-parse HEAD > vt-probe-artifacts/source-commit.txt
(cd vt-probe-artifacts && sha256sum vt_abi_probe.ko vt_probe_test vt_discovery_trace.so Module.symvers kernel.config module-check.json > SHA256SUMS)

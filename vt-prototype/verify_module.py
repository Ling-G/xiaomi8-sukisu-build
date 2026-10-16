"""Verify ELF machine, vermagic and every imported symbol CRC in a built module."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

def verify(module, symvers, output):
    blob = module.read_bytes()
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', blob)
    assert header[0][:6] == b'\x7fELF\x02\x01', 'Expected little-endian ELF64'
    assert header[1] == 1 and header[2] == 183, 'Expected AArch64 relocatable module'
    sections = [struct.unpack_from('<IIQQQQIIQQ', blob, header[6] + i * header[11]) for i in range(header[12])]
    names_header = sections[header[13]]
    names = blob[names_header[4]:names_header[4]+names_header[5]]
    by_name = {names[s[0]:].split(b'\0', 1)[0].decode(): s for s in sections}
    def contents(name):
        sec = by_name[name]
        return blob[sec[4]:sec[4]+sec[5]]
    vermagic = next(v[9:].decode() for v in contents('.modinfo').split(b'\0') if v.startswith(b'vermagic='))
    assert vermagic == '4.9.186-perf-g10af704 SMP preempt mod_unload modversions aarch64', vermagic
    expected = {}
    for row in symvers.read_text().splitlines():
        fields = row.split()
        expected[fields[1]] = int(fields[0], 16)
    versions = contents('__versions')
    assert len(versions) % 64 == 0
    checked = {}
    for at in range(0, len(versions), 64):
        crc = struct.unpack_from('<Q', versions, at)[0]
        name = versions[at+8:at+64].split(b'\0', 1)[0].decode()
        assert name not in checked, f'Duplicate version record: {name}'
        assert name in expected and crc == expected[name], (name, hex(crc), expected.get(name))
        checked[name] = hex(crc)
    assert checked.get('module_layout') == '0x2ee5b3bb', checked
    undefined = set()
    for sec in sections:
        if sec[1] != 2:
            continue
        string_section = sections[sec[6]]
        strings = blob[string_section[4]:string_section[4]+string_section[5]]
        for at in range(sec[4], sec[4]+sec[5], sec[9]):
            name_at, info, _, index, _, _ = struct.unpack_from('<IBBHQQ', blob, at)
            name = strings[name_at:].split(b'\0', 1)[0].decode()
            if name and index == 0 and info >> 4 != 2:
                undefined.add(name)
    assert undefined <= checked.keys(), f'Unversioned required imports: {undefined - checked.keys()}'
    report = {'passed': True, 'machine': 'AArch64', 'vermagic': vermagic,
              'module_sha256': hashlib.sha256(blob).hexdigest(),
              'symvers_sha256': hashlib.sha256(symvers.read_bytes()).hexdigest(),
              'checked_symbol_crcs': checked,
              'required_imports': sorted(undefined), 'hardware_validation': 'not performed',
              'scope': 'diagnostic subset; self-process copies only; not a complete VT driver'}
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('module', type=Path)
    parser.add_argument('symvers', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    verify(args.module, args.symvers, args.output)

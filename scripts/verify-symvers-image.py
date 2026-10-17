#!/usr/bin/env python3
"""Check Module.symvers against a dipper ARM64 Image.gz and its System.map."""
import argparse
import gzip
import hashlib
import json
import struct
from pathlib import Path


def verify(image_path, map_path, symvers_path):
    compressed = image_path.read_bytes()
    image = gzip.decompress(compressed)
    if image[56:60] != b"ARM\x64":
        raise ValueError("Expected an ARM64 Image.gz")
    symbols = {}
    for line in map_path.read_text().splitlines():
        address, _, name = line.split()
        symbols[name] = int(address, 16)
    base = symbols["_text"]
    expected = {}
    for line in symvers_path.read_text().splitlines():
        crc, name, module, export_type = line.split()
        if module != "vmlinux" or name in expected or not export_type.startswith("EXPORT_"):
            raise ValueError(f"Invalid kernel-only export: {line}")
        expected[name] = int(crc, 16)

    # On this relocatable ARM64 kernel the CRC slots are initially zero.
    # Their values live in R_AARCH64_RELATIVE addends, applied during startup.
    relocations = {}
    if "__rela_offset" in symbols:
        text_offset = struct.unpack_from("<Q", image, 8)[0]
        start = symbols["__rela_offset"] - text_offset
        size = symbols["__rela_size"]
        if start < 0 or size % 24 or start + size > len(image):
            raise ValueError("Invalid ARM64 relocation range")
        for offset in range(start, start + size, 24):
            address, info, addend = struct.unpack_from("<QQQ", image, offset)
            relocations[address] = (info, addend)

    actual = {}
    relocated = 0
    for name, address in symbols.items():
        if not name.startswith("__kcrctab_"):
            continue
        export = name[len("__kcrctab_"):]
        if address in relocations:
            info, addend = relocations[address]
            if info != 1027:  # ELF64_R_INFO(0, R_AARCH64_RELATIVE)
                raise ValueError(f"Unsupported CRC relocation for {export}: {info}")
            actual[export] = addend & 0xffffffff
            relocated += 1
        else:
            offset = address - base
            if offset < 0 or offset + 4 > len(image):
                raise ValueError(f"CRC slot outside Image: {export}")
            actual[export] = struct.unpack_from("<I", image, offset)[0]
    if not actual or actual != expected:
        changed = sorted(n for n in actual.keys() & expected.keys() if actual[n] != expected[n])
        raise ValueError(f"Export mismatch: image={len(actual)}, symvers={len(expected)}, changed={changed[:10]}")
    return {
        "passed": True,
        "verification": "All Module.symvers entries match the original Image CRC slots or ARM64 relocation addends",
        "exported_symbols": len(actual),
        "relocation_based_crc_entries": relocated,
        "module_layout_crc": f"0x{actual['module_layout']:08x}",
        "image_gzip_sha256": hashlib.sha256(compressed).hexdigest(),
        "system_map_sha256": hashlib.sha256(map_path.read_bytes()).hexdigest(),
        "module_symvers_sha256": hashlib.sha256(symvers_path.read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("image_gzip", type=Path)
    p.add_argument("system_map", type=Path)
    p.add_argument("module_symvers", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    report = verify(a.image_gzip, a.system_map, a.module_symvers)
    text = json.dumps(report, indent=2) + "\n"
    if a.output:
        if a.output.resolve() in {a.image_gzip.resolve(), a.system_map.resolve(), a.module_symvers.resolve()}:
            raise ValueError("Report must not overwrite an input")
        a.output.write_text(text, encoding="utf-8")
    print(text, end="")

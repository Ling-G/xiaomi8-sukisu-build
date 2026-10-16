#!/usr/bin/env python3
"""Repack this exact dipper stock boot locally; never uploads the firmware."""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

STOCK_SHA256 = "b959290a0b5f79a97f89806dc6fe385ddc4e1495f611b6c6fcb22d69411c60ed"

def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]

def align(size, page):
    return (size + page - 1) // page * page

def split_gzip(data):
    dec = zlib.decompressobj(31)
    image = dec.decompress(data) + dec.flush()
    if not dec.eof:
        raise ValueError("Incomplete gzip kernel")
    if image[56:60] != b"ARM\x64":
        raise ValueError("Kernel is not an ARM64 Image")
    return image, data[:len(data)-len(dec.unused_data)], dec.unused_data

def repack(stock_path, kernel_path, output_path, ksud_path=None):
    if output_path.resolve() in {stock_path.resolve(), kernel_path.resolve()}:
        raise ValueError("Output must not overwrite an input")
    if output_path.exists():
        raise FileExistsError(output_path)
    stock = stock_path.read_bytes()
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA256:
        raise ValueError("Stock boot SHA256 differs from the verified MIUI 12.5.2 image")
    if stock[:8] != b"ANDROID!" or u32(stock, 40) != 1:
        raise ValueError("Expected Android boot header v1")
    page, kernel_size, ramdisk_size = u32(stock, 36), u32(stock, 8), u32(stock, 16)
    if page != 4096 or u32(stock, 24) != 0 or u32(stock, 1632) != 0:
        raise ValueError("Unexpected second stage or recovery DTBO layout")
    header = bytearray(stock[:page])
    old_kernel = stock[page:page+kernel_size]
    _, old_gzip, dtbs = split_gzip(old_kernel)
    if dtbs[:4] != b"\xd0\x0d\xfe\xed":
        raise ValueError("Stock appended device tree was not found")
    new_gzip = kernel_path.read_bytes()
    _, checked_gzip, extra = split_gzip(new_gzip)
    if extra or checked_gzip != new_gzip:
        raise ValueError("Input must be Image.gz without appended DTBs")
    new_kernel = new_gzip + dtbs
    ramdisk_offset = page + align(kernel_size, page)
    ramdisk = stock[ramdisk_offset:ramdisk_offset+ramdisk_size]
    if len(ramdisk) != ramdisk_size:
        raise ValueError("Truncated stock ramdisk")
    stock_ramdisk = ramdisk
    if ksud_path is not None:
        from bootstrap_ramdisk import add_bootstrap
        ramdisk = add_bootstrap(ramdisk, ksud_path)
    digest = hashlib.sha1()
    for data in (new_kernel, ramdisk, b"", b""):
        digest.update(data)
        digest.update(struct.pack("<I", len(data)))
    struct.pack_into("<I", header, 8, len(new_kernel))
    struct.pack_into("<I", header, 16, len(ramdisk))
    header[576:608] = digest.digest() + bytes(12)
    result = bytes(header)
    for data in (new_kernel, ramdisk):
        result += data + bytes(align(len(data), page) - len(data))
    # The stock trailing ASN.1 AVB1 signature authenticates the original kernel.
    # Do not copy it to a modified image and imply that it is still valid.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result)
    report = {
        "image": output_path.name,
        "sha256": hashlib.sha256(result).hexdigest(),
        "size": len(result),
        "stock_sha256": STOCK_SHA256,
        "kernel_gzip_sha256": hashlib.sha256(new_gzip).hexdigest(),
        "stock_dtbs_sha256": hashlib.sha256(dtbs).hexdigest(),
        "stock_ramdisk_sha256": hashlib.sha256(stock_ramdisk).hexdigest(),
        "ramdisk_sha256": hashlib.sha256(ramdisk).hexdigest(),
        "backend_bootstrap": ksud_path is not None,
        "boot_header": 1,
        "signature": "Original AVB1 signature omitted; unlocked bootloader required",
        "device_validation": "Not performed; compilation/repacking alone does not confirm boot or Root",
    }
    output_path.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stock_boot", type=Path)
    p.add_argument("kernel_gzip", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--ksud", type=Path, help="Embed verified official 4.2.0 backend and first-boot installer")
    a = p.parse_args()
    repack(a.stock_boot, a.kernel_gzip, a.output, a.ksud)

#!/usr/bin/env python3
"""Verify the downloaded build before local boot repacking."""
import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path

EXPECTED_RELEASE = "4.9.186-perf-g10af704"
EXPECTED_TAG = b"builtin-2d1de629-dipper-port"
SYMBOLS = ["ksu_handle_execveat", "ksu_handle_faccessat", "ksu_handle_stat",
           "ksu_handle_vfs_read", "ksu_handle_vfs_fstat", "ksu_handle_sys_reboot",
           "ksu_lsm_hook_init", "ksu_ksud_init", "path_umount"]

def verify(folder):
    kernel_path = folder / "Image.gz"
    config_path = folder / "kernel.config"
    map_path = folder / "System.map"
    release = (folder / "kernelrelease.txt").read_text().strip()
    if release != EXPECTED_RELEASE:
        raise ValueError(f"Unexpected kernel release: {release!r}")
    image = gzip.decompress(kernel_path.read_bytes())
    if image[56:60] != b"ARM\x64":
        raise ValueError("Not an ARM64 Image")
    match = re.search(rb"Linux version [^\0\r\n]+", image)
    if not match or not match.group().startswith(("Linux version " + EXPECTED_RELEASE + " ").encode()):
        raise ValueError("Kernel's embedded release differs from the build record")
    if EXPECTED_TAG not in image:
        raise ValueError("Pinned SukiSU port marker absent from the kernel")
    config = config_path.read_text().splitlines()
    for flag in ("CONFIG_KSU=y", "# CONFIG_KPM is not set", "# CONFIG_KSU_SUSFS is not set"):
        if flag not in config:
            raise ValueError(f"Unexpected configuration: missing {flag}")
    symbols = {line.split()[-1] for line in map_path.read_text().splitlines() if line.strip()}
    missing = [name for name in SYMBOLS if name not in symbols]
    if missing:
        raise ValueError(f"Integration symbols absent: {missing}")
    sums = folder / "SHA256SUMS"
    for line in sums.read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip("*")
        if Path(name).name != name:
            raise ValueError("Checksum manifest contains an unsafe path")
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch: {name}")
    report = {
        "kernel_version": match.group().decode(errors="replace"),
        "release": release,
        "sukisu_port": EXPECTED_TAG.decode(),
        "required_symbols_found": SYMBOLS,
        "kernel_gzip_sha256": hashlib.sha256(kernel_path.read_bytes()).hexdigest(),
        "artifact_checks": "passed",
        "device_boot_root_hardware_tests": "not performed",
    }
    (folder / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("artifact_folder", type=Path)
    a = p.parse_args()
    verify(a.artifact_folder)

#!/usr/bin/env python3
"""Extract only the pinned official ARM64 UAPI-2 userspace backend locally."""
import argparse
import hashlib
import zipfile
from pathlib import Path
from bootstrap_ramdisk import KSUD_SHA256

APK_SHA256 = "4ca9810e6355fbff0bbe4bf5ce159808e64a40d85987a11894030cd990a6bdf3"
# https://github.com/SukiSU-Ultra/SukiSU-Ultra/releases/tag/v4.2.0
# Asset: SukiSU_v4.2.0_40900-release.apk. No APK is installed by this script.


def extract(apk, output):
    if output.exists():
        raise FileExistsError(output)
    if hashlib.sha256(apk.read_bytes()).hexdigest() != APK_SHA256:
        raise ValueError("Expected the pinned official v4.2.0 release APK")
    with zipfile.ZipFile(apk) as archive:
        payload = archive.read("lib/arm64-v8a/libksud.so")
    if hashlib.sha256(payload).hexdigest() != KSUD_SHA256:
        raise ValueError("Unexpected backend binary")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print(f"Verified official ARM64 ksud 4.2.0: {KSUD_SHA256}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("official_apk", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    extract(a.official_apk, a.output)

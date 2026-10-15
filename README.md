# Xiaomi Mi 8 SukiSU builtin build

Target: Xiaomi Mi 8 / dipper, MIUI V12.5.2.0.QEACNXM, Android 10, Linux 4.9.186.

Experimental device-specific kernel integration. A successful build is not evidence of successful boot, Root authorization, or module operation. Do not use this image on another device or ROM.

## Sources

- Xiaomi dipper-q-oss: dcfb1676925aec83b06ae04fd8ca989ced75067c
- SukiSU builtin: 2d1de629d4204d25cc0c8927b959d9135d9781f4
- Android 10 GCC 4.9 toolchains: fixed commits in pins.json
- Manager candidate: official SukiSU v4.2.0 (40900), UAPI 2. Basic driver commands and signing key are present in builtin; runtime verification remains required. Optional features differ from mainline v4.2.0.

The kernel displays builtin-2d1de629-dipper-port rather than claiming to be an unmodified release. Numeric compatibility version is pinned to 40900 for the selected manager generation.

## Build

Open Actions, select Build dipper SukiSU builtin, and run the workflow. Changes to build files also trigger it. The workflow builds Image.gz using the extracted stock configuration with SukiSU enabled. KPM, SUSFS, debug mode, and the optional adb-root feature are disabled for the initial build.

Artifacts include Image.gz, kernel.config, System.map, source pins, checksums, and the build log. A failed run can still produce a logs-only artifact; check the job result and Image.gz before using it.

The stock boot image is kept locally and is not part of this repository. The built Image.gz must be repacked locally with the exact stock boot image to preserve the device tree, ramdisk, and boot parameters. This workflow does not flash a device.

The public Xiaomi source commit differs from the original boot kernel's g10af704 commit. Matching the release string helps preserve external module naming, but does not prove module ABI compatibility. Wi-Fi, camera, fingerprint, charging, encryption, SELinux, and boot need device verification.

## Integration

scripts/prepare.py applies checked manual hooks to fs/exec.c, fs/open.c, fs/stat.c, fs/read_write.c and kernel/reboot.c, and backports path_umount using the target kernel's permission checks and reference-release behavior. SukiSU supplies its own LSM and input-handler registrations.

Scripts in this repository are GPL-2.0-only. Upstream source licensing remains with each upstream project. Full upstream source and pinned revisions remain publicly available at the linked repositories.

## Local boot repack

After downloading a successful Image.gz artifact, run:

```text
python scripts/repack.py /path/to/original/boot.img /path/to/Image.gz /path/to/boot-sukisu.img
```

The script checks the exact stock SHA256, preserves the stock ramdisk and appended DTBs, updates the header checksum, and omits the invalidated original AVB1 signature. An unlocked bootloader is required to test this modified image. It never uploads the stock image or flashes the device.

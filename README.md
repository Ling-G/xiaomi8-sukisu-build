# 小米 8 SukiSU 内核：管理器后端兼容实验版

本分支 `experiment/manager-backend-compat` 基于已验证的延后安装版。新增功能已通过本地隔离测试、保留数据的临时启动测试，以及 **2026-10-24 清空数据的全量刷机测试**。首次开机成功，后台自动补装；随后安装官方管理器，`libksud.so` 自动修复，无需手动补装后台或替换库。用户确认 MT Root、SukiSU 识别、音乐/视频及 Wi-Fi 正常；正常重启后 Root 可用、授权文件完全一致、兼容后端保留。APK 校验值保持不变，SELinux 为 Enforcing。

- 开机完成后启动检查，每 60 秒查询一次管理器安装路径，覆盖开机后才安装管理器的情况。
- 只处理官方 `SukiSU_v4.2.1_40994-release.apk`（完整 APK SHA256 白名单）及其已知 ARM64 后端；未知版本或未解压原生库时跳过。
- 将提取目录的 `libksud.so` 原子替换为已校验的官方 4.2.0 UAPI 2 后端，保留原权限和 SELinux 标签；不修改 APK、签名或授权数据。成功替换会强制停止管理器一次，重新打开即可。
- 原后端备份于 `/data/adb/dipper-manager-compat/original-libksud.so`，日志为 `/data/adb/dipper-bootstrap.log`。
- 停用：用 Root 创建 `/data/adb/dipper-manager-compat.disable`，等待一分钟或重启；需要恢复原库时，再覆盖安装官方管理器 APK。
- 这是已知版本适配，不是通用 UAPI 5 支持；4.2.1 新增、4.2.0 不具备的管理命令仍可能不可用。

实验镜像命名为 `boot-dipper-susfs-manager-compat-r2.img`。使用本分支的封装脚本，内核仍沿用已验证的构建 #7，只更新 ramdisk 检查脚本；可继续使用原来的 `Module.symvers`。

本地隔离测试：`python scripts/test-manager-compat.py /path/to/SukiSU_v4.2.0_40900-release.apk /path/to/SukiSU_v4.2.1_40994-release.apk`。测试模拟 Android 命令和 SELinux 标签，不代表实机兼容性验证。官方 APK 来源：[4.2.0](https://github.com/SukiSU-Ultra/SukiSU-Ultra/releases/tag/v4.2.0)、[4.2.1](https://github.com/SukiSU-Ultra/SukiSU-Ultra/releases/tag/v4.2.1)。

下面的“已验证版本”描述的是基础内核；本分支新增自动修复功能的验证范围见上文。


适用于 **小米 8（dipper）/ MIUI V12.5.2.0.QEACNXM / Android 10 / Linux 4.9.186**，需要已解锁 Bootloader。

集成 SukiSU `builtin`、SUSFS **v2.3.0 / NON-GKI**，音频和 Wi-Fi 驱动直接内置，无需配套 `.ko`。其他 ROM 和设备未验证。

## 已验证版本

使用 **延后安装版 `boot-dipper-susfs-bootstrap-late.img`**：

- [构建 #7](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/38925186346)，源码提交 `3d4c051839b49da0b31d9273b1cfddf4f689899c`。
- 2026-10-17 用户确认：通过 `flash_all.bat` 全量刷机后，直接首次启动成功，各项已测功能正常。
- 已测音乐、视频、Wi-Fi、MT Root、管理器识别及授权保存；SELinux 保持 Enforcing，外部模块列表为空。
- 后台缺失时，在系统启动完成后自动安装官方 `ksud 4.2.0`；已有后台则保留。首次补装后，模块早期启动阶段从下一次正常重启开始。

**旧版 `boot-dipper-susfs-bootstrap.img` 存在全量刷机后首次启动失败的问题，请使用带 `-late` 的版本。** 原失败日志未保留，具体根因未确认。

长期稳定性、通话、录音、蓝牙音频、热点、休眠续航、exFAT 和第三方模块尚未完整验证；SUSFS 不保证通过特定应用的检测。

## 构建

在 [Actions](https://github.com/Ling-G/xiaomi8-sukisu-build/actions) 中选择工作流，点击 **Run workflow**：

| 工作流 | 内容 |
| --- | --- |
| [Build dipper builtin drivers with SUSFS](.github/workflows/build-susfs.yml) | 当前已验证方案：SUSFS、内置音频和 Wi-Fi，支持后台自动部署封装 |
| [Build dipper builtin audio and Wi-Fi](.github/workflows/build-builtin.yml) | 不带 SUSFS 的内置驱动版 |

其他工作流为早期实验方案。仅修改 README 不会触发构建。

成功构建后下载产物：SUSFS 版为 `dipper-susfs-experimental`，不带 SUSFS 版为 `dipper-builtin-experimental`。产物包含 `Image.gz`、配置、检查报告及校验清单，保留 **14 天**。使用前确认任务成功，并核对 `SHA256SUMS`、`BUILTIN-SHA256SUMS`；SUSFS 版还需核对 `SUSFS-SHA256SUMS`。

[符号表导出构建 #8](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/38941989142) 另含 `Module.symvers` 和 CRC 检查报告；全部 11,641 个导出 CRC 已与构建 #7 原镜像核对一致，可配套上述延后安装版使用，无需重刷。

## 封装与启动

仓库不提供原厂或修改后的 boot 镜像，需要用上述系统的原厂 `boot.img` 本地封装。脚本会核对原厂镜像及后台校验值，保留原厂 init 和 DTB，移除修改后失效的 AVB1 签名。

从 [官方 v4.2.0 发布页](https://github.com/SukiSU-Ultra/SukiSU-Ultra/releases/tag/v4.2.0) 下载 `SukiSU_v4.2.0_40900-release.apk`，提取后台并封装自动部署版：

```text
python scripts/extract-backend.py /path/to/SukiSU_v4.2.0_40900-release.apk /path/to/ksud-4.2.0
python scripts/repack.py /path/to/original/boot.img /path/to/artifacts/Image.gz /path/to/boot-dipper-susfs-bootstrap-late.img --ksud /path/to/ksud-4.2.0
```

`--ksud` 需要包含晚期安装入口的新内核；单独的 `Image.gz` 不含后台。省略此选项可保留完整原厂 ramdisk，但需自行部署后台。

先用 `fastboot boot` 临时测试，**保留原厂完整启动参数并追加 `androidboot.mode=normal`**，避免进入充电模式：

```text
fastboot --cmdline "<原厂完整启动参数> androidboot.mode=normal" boot boot-dipper-susfs-bootstrap-late.img
```

临时启动不刷写分区，重启后使用 boot 分区原有内核。永久刷入后则继续使用已刷入的内核。`flash_all.bat` 全量刷机会清空用户数据，应先备份。

## 兼容性说明

- 使用官方 **4.2.1 管理器 + 4.2.0 后台**。当前内核兼容版本号为 `40900`、UAPI 为 **2**；管理器要求 UAPI 5，因此可能提示更新内核，该提示不代表本项目已支持 UAPI 5。4.2.0 管理器在此系统曾出现白屏。
- 后台安装日志：`/data/adb/dipper-bootstrap.log`。SUSFS 可用 Root Shell 查询：`/data/adb/ksud susfs version`。
- Wi-Fi 仍使用原厂 vendor 的固件和配置。升级内置驱动版时禁用旧 `dipper_driver_autoload` 模块，不要混用其他内核的 `.ko` 或跳过 ABI 校验。
- KPM、调试模式、可选 adb-root 均关闭；本 4.9 端口不提供可选 SELinux 隐藏功能。

## 源码与许可

| 组件 | 固定来源 |
| --- | --- |
| 内核 | [MiCode / dipper-q-oss](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/dcfb1676925aec83b06ae04fd8ca989ced75067c) |
| SukiSU | [SukiSU-Ultra / builtin](https://github.com/SukiSU-Ultra/SukiSU-Ultra/tree/2d1de629d4204d25cc0c8927b959d9135d9781f4) |
| 音频 | [MiCode audio-kernel / dipper-q-oss](https://github.com/MiCode/vendor_qcom_opensource_audio-kernel/tree/27531fc846efac18206c65e0c09ad36cce514c76) |
| Wi-Fi | [MiCode WLAN / dipper-q-oss](https://github.com/MiCode/vendor_qcom_opensource_wlan/tree/e9c485b6ff4282c649ea4cff5116a613b0678cb4) |
| SUSFS | [wxx9248 Linux 4.9 移植](https://github.com/wxx9248/susfs4ksu/tree/71345ded5af28f55d76ebcdc7a9df9cea56111e1)，[上游项目](https://gitlab.com/simonpunk/susfs4ksu) |
| 工具链 | Android 10 GCC 4.9，固定提交见 [pins.json](pins.json) |

本仓库脚本采用 **GPL-2.0-only**；上游代码遵循各自许可。

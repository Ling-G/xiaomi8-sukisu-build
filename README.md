# 小米 8 SukiSU 内核构建

适用于 **小米 8（dipper）/ MIUI V12.5.2.0.QEACNXM / Android 10 / Linux 4.9.186**。基于小米公开源码，集成 SukiSU `builtin` 分支，并支持将音频和 Wi-Fi 驱动直接编入内核。

当前为实验性设备适配，仅在上述系统上完成临时启动测试。其他 ROM、设备及长期稳定性尚未验证。

## 当前状态（2026-10-16）

音频与 Wi-Fi 内置版已完成编译、产物校验和实机临时启动验证：

- 音乐、视频播放及声音输出正常。
- Wi-Fi 开机自动启动并连接，上网正常，无需手动触发。
- SukiSU 管理器开机识别正常，Root 授权可保存并在再次临时启动后保留。
- 测试时旧驱动自动加载模块已禁用，外部内核模块列表为空，音频和 Wi-Fi 不依赖配套 `.ko`。
- SELinux 保持 Enforcing；未使用诊断用的 Shell 自动授权启动参数。

以上是基本功能测试结果，不代表所有硬件与使用场景均已覆盖。通话、录音、蓝牙音频、热点、深度休眠、续航、exFAT 及第三方模块仍需进一步验证。

[已验证的内置版构建 #2](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/38862869932)，源码提交 [`b337f2e`](https://github.com/Ling-G/xiaomi8-sukisu-build/commit/b337f2ef8e1868047889370e9f645f8e39d7fd90)。实机验证使用本地原厂 boot 镜像封装后的镜像，原厂及修改后的 boot 镜像均未上传到本仓库。

## 构建方式

在 [Actions](https://github.com/Ling-G/xiaomi8-sukisu-build/actions) 中选择对应工作流并运行：

| 工作流 | 内容 |
| --- | --- |
| **Build dipper builtin audio and Wi-Fi** | 当前已验证方案：完整内核，内置音频和 Wi-Fi 驱动 |
| Build dipper audio core and matching modules | 之前的分离驱动方案：音频核心及配套音频、Wi-Fi 模块 |
| Build matching dipper Wi-Fi module | 内核及配套 Wi-Fi 模块 |
| Build dipper SukiSU builtin | 基础 SukiSU 内核，不包含完整的音频、Wi-Fi 修复 |

当前内置方案对应 [build-builtin.yml](.github/workflows/build-builtin.yml)，入口为 [scripts/build-builtin.sh](scripts/build-builtin.sh)。仅修改 README 不会触发该工作流；需要时手动运行。

成功构建的 `dipper-builtin-experimental` 产物包含 `Image.gz`、`kernel.config`、`System.map`、音频内置配置、整合与检查报告、源码版本信息、校验清单及构建日志。产物保留 14 天，过期后需要重新构建。失败任务可能只有日志，使用前应确认任务成功并检查实际文件。

构建会检查 Wi-Fi 配置为 `CONFIG_QCA_CLD_WLAN=y`、音频原有 13 项模块配置改为内置，并验证关键驱动初始化入口确实出现在最终 `System.map` 中。**编译检查不能替代实机测试。**

## 内置驱动与开机流程

[scripts/prepare-builtin.py](scripts/prepare-builtin.py) 将小米独立发布的音频源码和 WLAN 源码接入内核构建，调整音频依赖注册顺序，并修正 WLAN 的独立输出目录构建路径。

Wi-Fi 的原生内置模式仍需要在文件系统就绪后触发 `/sys/kernel/boot_wlan/boot_wlan`。镜像中的 Android init 配置通过现有 KSU 执行上下文完成这一步，不关闭 SELinux，也不加载外部驱动。Wi-Fi 仍读取原厂 vendor 中的固件和配置文件，固件没有编入内核。

之前用于加载 `.ko` 的 `dipper_driver_autoload` 模块在内置版测试中保持禁用。切换到内置版时应禁用它，避免重复执行旧加载流程；若恢复之前的分离驱动版，应重新启用其配套模块。

## SukiSU 兼容性与后台

本项目使用固定版本的 `builtin` 源码进行 Linux 4.9 适配，显示版本为 `builtin-2d1de629-dipper-port`，兼容版本号为 `40900`，UAPI 为 **2**。这不是官方未修改的最新内核版本。

测试环境使用官方 **4.2.1 管理器**与匹配 UAPI 2 的官方 **4.2.0 后台组件 `ksud`**。4.2.0 管理器在该 Android 10 环境曾出现白屏；4.2.1 管理器可正常识别和授权，但其要求的 UAPI 5 与当前内核不同，因此仍可能提示更新内核。该提示不代表本项目已实现 UAPI 5。

驱动内置后，SukiSU 后台仍负责授权持久化及模块生命周期等功能。当前测试手机已部署匹配的 `/data/adb/ksud`；仅启动本仓库编译的内核，不会自动完成所有后台安装。未部署相同后台环境的手机尚未验证，不应仅凭管理器能打开就判断后台完整可用。

[scripts/prepare.py](scripts/prepare.py) 包含手动内核 hook、旧内核 API 兼容、管理器开机扫描、旧版 fscrypt 文件访问与后台服务启动修复。KPM、SUSFS、调试模式和可选 adb-root 功能关闭；4.9 端口不提供可选 SELinux 隐藏功能。

## 本地封装与临时启动

仓库不包含原厂 boot 镜像。下载成功构建的产物并解压后，先检查校验清单与整合报告，也可运行：

```text
python scripts/verify.py /path/to/artifacts
python scripts/repack.py /path/to/original/boot.img /path/to/artifacts/Image.gz /path/to/boot-sukisu.img
```

封装脚本核对原厂镜像 SHA256，保留原厂 ramdisk 和追加的 DTB，更新镜像头校验，并移除修改后已失效的原 AVB1 签名。它不会上传镜像或操作手机分区。

测试需要已解锁的 Bootloader。在 Fastboot 模式下使用 `fastboot boot` 临时启动。该系统测试时需通过 `--cmdline` **保留原厂完整启动参数并追加 `androidboot.mode=normal`**，避免进入充电模式。以下参数位置为占位说明，须替换为原厂实际参数：

```text
fastboot --cmdline "<原厂完整启动参数> androidboot.mode=normal" boot boot-sukisu.img
```

当前验证仅使用临时启动，未刷写 boot 或 vendor 分区，也未清除数据。正常重启会回到 boot 分区原有内核。永久刷入与其他刷机方式未在本项目中验证。

## 固定源码版本

| 组件 | 来源与版本 |
| --- | --- |
| 内核 | [MiCode/Xiaomi_Kernel_OpenSource](https://github.com/MiCode/Xiaomi_Kernel_OpenSource)，`dipper-q-oss`，`dcfb1676925aec83b06ae04fd8ca989ced75067c` |
| SukiSU | [SukiSU-Ultra/SukiSU-Ultra](https://github.com/SukiSU-Ultra/SukiSU-Ultra)，`builtin`，`2d1de629d4204d25cc0c8927b959d9135d9781f4` |
| 音频 | [MiCode/vendor_qcom_opensource_audio-kernel](https://github.com/MiCode/vendor_qcom_opensource_audio-kernel)，`dipper-q-oss`，`27531fc846efac18206c65e0c09ad36cce514c76` |
| WLAN | [MiCode/vendor_qcom_opensource_wlan](https://github.com/MiCode/vendor_qcom_opensource_wlan)，`dipper-q-oss`，`e9c485b6ff4282c649ea4cff5116a613b0678cb4` |
| 工具链 | Android 10 GCC 4.9，64/32 位固定提交见 [pins.json](pins.json) |

音频和 WLAN 的固定版本还记录在构建脚本中。公开内核源码与原厂 `g10af704` 构建并不完全相同；保留版本字符串不等于模块 ABI 相同，不能直接混用原厂或其他内核的 `.ko`，也不应跳过模块版本校验。

## 许可

本仓库脚本采用 GPL-2.0-only。上游内核、SukiSU、音频及 WLAN 源码分别遵循各自项目中的许可；完整源码及固定版本可通过上述链接获取。

# 小米 8 SukiSU 内核构建

适用于 **小米 8（dipper）/ MIUI V12.5.2.0.QEACNXM / Android 10 / Linux 4.9.186**。基于小米公开源码，集成 SukiSU `builtin` 分支，并支持将音频和 Wi-Fi 驱动直接编入内核。

当前为实验性设备适配，已在上述系统上完成临时启动测试；用户随后永久刷入，并确认连续两次正常重启后各项已测功能仍正常。其他 ROM、设备及长期稳定性尚未验证。

## 最新验证（2026-10-17）

用户已确认通过 `flash_all.bat` 全量刷机后，直接使用延后安装版 `boot-dipper-susfs-bootstrap-late.img` 首次启动正常，各项功能正常。缺失后台在系统启动完成后补装，已有后台保留正常早期流程。构建与验证范围见下文“延后安装版”。

## 内置驱动基础版验证（2026-10-16）

音频与 Wi-Fi 内置版已完成编译、产物校验和实机临时启动验证。用户另已确认永久刷入后连续两次重启，音乐、视频、Wi-Fi 上网、SukiSU 识别和 Root 授权均正常：

- 音乐、视频播放及声音输出正常。
- Wi-Fi 开机自动启动并连接，上网正常，无需手动触发。
- SukiSU 管理器开机识别正常，Root 授权可保存，并在再次临时启动及永久刷入后的两次重启中保留。
- 测试时旧驱动自动加载模块已禁用，外部内核模块列表为空，音频和 Wi-Fi 不依赖配套 `.ko`。
- SELinux 保持 Enforcing；未使用诊断用的 Shell 自动授权启动参数。

以上是基本功能测试结果，不代表所有硬件与使用场景均已覆盖。通话、录音、蓝牙音频、热点、深度休眠、续航、exFAT 及第三方模块仍需进一步验证。

[已验证的内置版构建 #2](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/38862869932)，源码提交 [`b337f2e`](https://github.com/Ling-G/xiaomi8-sukisu-build/commit/b337f2ef8e1868047889370e9f645f8e39d7fd90)。实机验证使用本地原厂 boot 镜像封装后的镜像，原厂及修改后的 boot 镜像均未上传到本仓库。

## SUSFS 实验版（可选）

已新增独立工作流 **Build dipper builtin drivers with SUSFS**，在音频/Wi-Fi 内置版上接入 SUSFS **v2.3.0 / NON-GKI**。使用 [wxx9248 的 Linux 4.9 移植](https://github.com/wxx9248/susfs4ksu)，固定提交 `71345ded5af28f55d76ebcdc7a9df9cea56111e1`，并针对小米源码、GCC 4.9、旧版 SELinux SID 接口及存储监测流程进行适配。

[实验构建 #5](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/38890083902)（提交 `d52b1842972337657858fd0f3ccee3243b39a5e5`）已通过电脑端临时启动检查：版本与功能查询正常，`uname` 临时修改及恢复测试通过，SID 缓存和存储监测的监听、事件、延迟清理流程正常；Root 授权保留、Wi-Fi 自动连接、声卡注册、无外部模块及 SELinux Enforcing 均已核对。用户已确认音乐、视频、Wi-Fi 上网和 SukiSU 识别均正常，管理器 SUSFS 页面显示 v2.3.0。

**用户已确认将本 SUSFS 版永久刷入，重启后测试功能正常。** 该结果来自用户实机反馈；上文“连续两次重启正常”的记录属于之前不带 SUSFS 的内置版。永久刷入 SUSFS 版后，正常重启继续使用已刷入的 SUSFS 内核。

当前官方 4.2.0 `ksud` 已提供匹配的控制命令，在 Root Shell 中可查询：

```text
/data/adb/ksud susfs status
/data/adb/ksud susfs version
/data/adb/ksud susfs features
```

构建产物另含 `susfs-check.json`、`SUSFS-SHA256SUMS` 和只读 `susfs-query` 诊断工具。源码入口为 [scripts/build-susfs.sh](scripts/build-susfs.sh) 与 [scripts/prepare-susfs.py](scripts/prepare-susfs.py)，先预检所有修改对象，再构建完整内核。

内核支持已编入，不等于所有隐藏规则组合均已测试。实验流程未安装规则模块或写入自定义持久配置，不承诺通过特定应用的检测。4.2.1 管理器与当前内核 UAPI 的原有差异也仍然存在。长期稳定性和各项隐藏规则仍需进一步验证。

## 构建方式

在 [Actions](https://github.com/Ling-G/xiaomi8-sukisu-build/actions) 中选择对应工作流并运行：

| 工作流 | 内容 |
| --- | --- |
| Build dipper builtin drivers with SUSFS | SUSFS v2.3.0 实验版，保留内置音频/Wi-Fi |
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

驱动内置后，SukiSU 后台仍负责授权持久化及模块生命周期等功能。当前测试手机已部署匹配的 `/data/adb/ksud`；仅启动本仓库编译的内核，不会自动完成所有后台安装。清空 userdata 后的实机检查发现：安装 4.2.1 管理器并保存超级用户授权，并未自动生成 `/data/adb/ksud`；此时 `su` 入口虽然可见，执行仍会报文件不存在。使用匹配的官方 4.2.0 `ksud` 通过已授权 Shell 的 `debug su` 接口取得 Root，执行该后台的 `install` 后，常规 `su -c id` 已恢复 UID 0，SUSFS 查询及 SELinux Enforcing 正常。此现象说明旧镜像缺少首次部署流程；新增的可选自动部署封装现已补齐该流程，见下文。

[scripts/prepare.py](scripts/prepare.py) 包含手动内核 hook、旧内核 API 兼容、管理器开机扫描、旧版 fscrypt 文件访问与后台服务启动修复。稳定的基础/驱动内置版关闭 SUSFS，独立 SUSFS 实验版启用相应配置。KPM、调试模式和可选 adb-root 功能均关闭；4.9 端口不提供可选 SELinux 隐藏功能。


### 清空数据后的后台自动部署

**旧构建 #6 的已知问题：全量刷机后的首次启动失败。延后安装构建 #7 已获用户首次启动成功反馈，见下节。** 用户实测使用 `flash_all.bat` 清空并重刷后直接使用 `boot-dipper-susfs-bootstrap.img` 无法进入系统，第二次重启进入 Recovery；先使用不带自动安装的 `boot-dipper-susfs.img` 完成首次开机，再切换自动安装版可以正常启动。现有“移走后台和 bin 后自动补齐”的测试只覆盖已初始化系统，不能代表全新 userdata 的首次启动。请勿将旧的早期安装镜像 `boot-dipper-susfs-bootstrap.img` 用作全量刷机后的首次启动镜像；后续使用延后安装版 `boot-dipper-susfs-bootstrap-late.img`。


构建 #6 的原实现为可选后台引导封装（后续时序候选见下节）：将经过 SHA256 校验的官方 4.2.0 ARM64 `ksud` 及安装器加入 ramdisk。内核在 Android 10 切换系统根目录前保留这两个资源，读取 init 配置时交接到 `/dev`；`post-fs-data` 同步安装缺失后台，再继续原有 KSU 开机流程。原厂 first-stage `init` 文件保持原样，无需修改 system/vendor 或关闭 SELinux。

已有 `/data/adb/ksud` 时保留现有版本，不覆盖后台、授权或模块配置。本功能需要同时使用支持资源交接的新内核和带 `--ksud` 封装的 boot；单独下载 `Image.gz` 不会自动带上后台。

从 [官方 v4.2.0 发布页](https://github.com/SukiSU-Ultra/SukiSU-Ultra/releases/tag/v4.2.0) 下载 `SukiSU_v4.2.0_40900-release.apk` 后，在本地提取后台并封装：

```text
python scripts/extract-backend.py /path/to/SukiSU_v4.2.0_40900-release.apk /path/to/ksud-4.2.0
python scripts/repack.py /path/to/original/boot.img /path/to/artifacts/Image.gz /path/to/boot-sukisu-bootstrap.img --ksud /path/to/ksud-4.2.0
```

APK 和提取的后台分别按固定校验值核对，不依赖可变的 latest 版本。安装器日志位于 `/data/adb/dipper-bootstrap.log`，仅记录安装或保留结果。

[后台自动部署构建 #6](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/38902385437)（内核提交 `193726b00e64497ba2e477ff998183fbaef37084`）已完成两次临时启动：已有后台时保留；后台与配套 `bin` 目录经备份移走后，开机约 5.7 秒自动安装完成，再进入正常 KSU `post-fs-data` 流程。常规 Root、SUSFS v2.3.0 查询和授权文件校验通过，SELinux Enforcing，原 boot 分区未改写。测试模拟了组件缺失，没有再次清空整台手机；用户已确认 MT Root 操作、SukiSU 识别、音乐/视频播放及 Wi-Fi 上网均正常，无需重新授权或手动补装后台。上述验证最初使用临时启动；用户后续在旧版完成首次初始化后刷入自动安装版并正常启动，但全量刷机后的直接首次启动失败，见本节已知问题。


### 延后安装版（用户已验证全量刷机首次启动）

[延后安装构建 #7](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/38925186346)，源码提交 `3d4c051839b49da0b31d9273b1cfddf4f689899c`。针对上述已知问题，将“缺失后台的首次安装”从 `post-fs-data` 移到 `sys.boot_completed=1`；已有后台仍保留正常早期流程。首次补装不在系统启动后补跑模块早期挂载，完整模块早期阶段从下一次正常重启开始。原失败启动日志未留存，具体根因仍未证实；下述成功测试说明延后安装方案在本机本系统上解决了已报告的首次启动场景。

已完成两次保留用户数据的临时启动：后台与工具经备份移走后，早期约 5.9 秒跳过安装，系统启动完成后约 22.5 秒自动补装；下一次启动约 5.8 秒正常执行早期后台流程。Root、授权文件校验、SUSFS v2.3.0、声卡注册、无外部模块和 SELinux Enforcing 均通过，boot 分区未改写。**2026-10-17 用户已确认：使用 `flash_all.bat` 全量刷机后，直接刷入 `boot-dipper-susfs-bootstrap-late.img` 可以正常首次进入系统，各项功能正常。** 此次由用户自行永久刷入，无需先用旧版完成首次开机。该结果属于用户实机反馈，不代表跨 ROM、长期稳定性或全部模块兼容性已验证。

最新 `repack.py --ksud` 要求内核包含晚期安装入口，旧构建会被拒绝。需要自动部署功能时，请使用延后安装构建的内核和最新封装脚本；仍需按上述方法从固定官方 APK 提取后台。镜像只在本地封装，仓库不提供原厂或修改后的 boot 镜像。

## 本地封装与临时启动

仓库不包含原厂 boot 镜像。下载成功构建的产物并解压后，先在产物目录核对 `SHA256SUMS` 和 `BUILTIN-SHA256SUMS`；SUSFS 版还应核对 `SUSFS-SHA256SUMS`，并查看对应整合报告。提供 `sha256sum` 的环境中可使用 `sha256sum -c <清单文件名>`。封装时运行：

```text
python scripts/repack.py /path/to/original/boot.img /path/to/artifacts/Image.gz /path/to/boot-sukisu.img
```

封装脚本核对原厂镜像 SHA256，保留追加的 DTB，更新镜像头校验，并移除修改后已失效的原 AVB1 签名。默认保留完整原厂 ramdisk；启用 `--ksud` 时保留原厂各 CPIO 条目和 init，额外加入固定后台及安装器。它不会上传镜像或操作手机分区。

测试需要已解锁的 Bootloader。在 Fastboot 模式下使用 `fastboot boot` 临时启动。该系统测试时需通过 `--cmdline` **保留原厂完整启动参数并追加 `androidboot.mode=normal`**，避免进入充电模式。以下参数位置为占位说明，须替换为原厂实际参数：

```text
fastboot --cmdline "<原厂完整启动参数> androidboot.mode=normal" boot boot-sukisu.img
```

上述命令仅用于临时启动，不刷写分区；临时启动后正常重启会回到 boot 分区原有内核。用户另已自行永久刷入本内置版，并确认连续两次重启后上述功能均正常。永久刷入后，正常重启会继续使用已刷入的内核，不会自动恢复原厂内核。用户还于 2026-10-17 确认通过本地 `flash_all.bat` 全量刷机后直接使用延后安装版首次启动正常；该刷机由用户自行执行，仓库脚本不执行分区刷写。其他系统与刷机方式尚未验证。

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

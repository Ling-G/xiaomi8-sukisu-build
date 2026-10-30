# 小米 8 VT 外部驱动（4.9.186）

本分支 `vt-abi-probe-4.9` 开发独立加载的 **`vt_abi_probe.ko`**。**v0.3 已通过真机加载、自测和原版 VT 4.7.7 识别测试**，无需重新封装或刷入 boot 镜像。**v0.4 增加了原驱动中的模块隐藏与设备隐藏逻辑，已通过 Actions 构建与全部离线 ABI 校验，尚待真机验证。**

**这仍是部分实现：硬件断点、tracking 和完整 PTE 接口尚未完成。识别成功不代表 VT 的全部功能可用。**

原有 SukiSU/SUSFS 内核构建说明见 [main 分支 README](https://github.com/Ling-G/xiaomi8-sukisu-build/blob/main/README.md)。本分支的驱动工作独立进行，不修改 main。

## 百度地图自动化测试

**[百度地图流程程序](baidumap-test/README.md)** 默认目标为 **何记开锁**，**无限循环，连续五轮未找到后停止**。每轮清除全部应用数据和缓存 → 同意协议 → 仅在使用中允许定位 → 暂不开启 → 顶部输入“开锁”并搜索 → 只检查第一屏。找到后点击并清零连续未找到计数；没有则打印 `LOG 没有找到`。不翻页，网络或页面加载错误不算“未找到”。

已启动真机循环，当前结果以本地实时汇总为准；仓库中的[验证记录](baidumap-test/validation.json)为运行快照。五次停止、找到清零及错误不算未找到的逻辑测试均通过。此前“即时达”十轮全成功记录保留在[历史验证](baidumap-test/validation-jishida-10-rounds.json)。

点击驱动为 **v0.2**，修正 Android 对退化触摸槽范围的识别，支持连续点击；配套中文输入与页面读取辅助程序无需安装 APK、输入法或常驻服务。

## 屏幕点击接口（独立触屏模块）

新增 `vt_touch.ko` 和原生测试程序 `vt_touch_test`，使用固定可见节点 `/dev/vt_touch`。点击模块可独立加载、卸载，不依赖原版 VT 自动调用。通过标准 Linux 输入设备 `VT Touchscreen` 发送完整单次按下/抬起；默认坐标为小米 8 自然竖屏 1080×2248。

接口、自测和单次点击用法见 **[屏幕点击说明](vt-prototype/TOUCH.md)**。**2026-10-30 已通过[编译](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/41008536431)、真机接口自测、完整触摸事件捕获和 Android 界面点击验证，卸载及重新加载均正常。** 驱动与测试程序已在手机就绪，详情及 SHA256 见说明。

## 已验证环境

| 项目 | 已验证值 |
| --- | --- |
| 设备 | 小米 8 / dipper，AArch64 |
| 系统 | MIUI V12.5.2.0.QEACNXM / Android 10 |
| 当前内核 | `4.9.186-perf-g10af704` |
| 模块版本 | `0.3`（已验证）、`0.4`（隐藏逻辑，构建与离线 ABI 校验通过，待真机验证） |
| 主程序 | 原版 VT 4.7.7 |
| 模块 vermagic | `4.9.186-perf-g10af704 SMP preempt mod_unload modversions aarch64` |

仅有相同的 `4.9.186` 版本号不足以确认兼容，内核配置及导出符号 CRC 也必须匹配。其他内核、ROM 和设备未验证。

## 下载

已验证的 v0.3 来自 [Actions 构建 #9](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/39005888286)，源码提交为 [fbcf057](https://github.com/Ling-G/xiaomi8-sukisu-build/commit/fbcf057ef49054541c7966dd8731c5dc29199785)。

在该任务页面的 **Artifacts** 中下载 `vt-abi-probe-dipper-4.9`，解压后进入 `vt-probe-artifacts/`：

| 文件 | 用途 |
| --- | --- |
| `vt_abi_probe.ko` | 独立内核模块 |
| `vt_probe_test` | 原生 AArch64 自测程序，不会自行加载或卸载模块 |
| `vt_hold_test` | v0.4 起提供：打开诊断端点并保持 5 秒，用于观察节点隐藏 |
| `module-check.json`、`SHA256SUMS` | ABI 检查结果和校验清单 |
| `kernel.config`、`kernelrelease.txt`、`Module.symvers` | 构建配置及符号记录 |

Actions 产物保留 **14 天**。其中的 `Module.symvers` 是本模块所需符号的子集，不能替代完整内核符号表。开发用的 `vt_discovery_trace.so` 无需安装，正常启动不依赖它。

以上提交与校验值对应已验证的 v0.3。

v0.4 的构建来自 [Actions 构建 #10](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/runs/39041250572)，源码提交为 [`4828a68`](https://github.com/Ling-G/xiaomi8-sukisu-build/commit/4828a68cde5192abe32df8e4928938b5e554d7b3)。该轮 job 全部步骤成功，构建内的校验断言因此为真：`vermagic` 仍为 `4.9.186-perf-g10af704 SMP preempt mod_unload modversions aarch64`、ELF 为 AArch64、**每一条 `__versions` 记录都按名与 CRC 命中给定符号表**、`module_layout` 为 `0x2ee5b3bb`、且不存在未版本化的导入符号。

v0.4 已在真机上完成两轮验证（2026-10-17，同一台 dipper）：

| 检查 | `hide_module=0`（第一轮） | `hide_module=1`（第二轮） |
| --- | --- | --- |
| 模块出现在 `/proc/modules` | 是 | **否** |
| 模块出现在 `/sys/module` | 是 | **否** |
| `/dev/vt_abi_probe` 正常 | 是 | 是 |
| 原生自测 | PASS | PASS |
| 节点在 open 期间消失 | 是 | 是 |
| 节点在 close 后恢复 | 是 | 是 |
| 原版 VT 识别（未修改脚本） | 是 | **是** |
| VT 打开发现节点后该节点消失 | 是 | 是 |
| `rmmod` | 成功 | **失败（`ENOENT`，设计如此）** |

结果为：**构建产物校验通过，且隐藏行为在真机上按原驱动方式生效**。硬件断点、tracking 与完整 PTE 接口仍未实现，识别成功不代表这些功能可用。

v0.4 的 `vt_abi_probe.ko` SHA256（267,376 字节）：

```text
28bd95b8c51b4e7fce41e00ace09a9a84087af5b6f875081fd349a1b2290f54e
```

已验证 v0.3 的 `vt_abi_probe.ko` SHA256：

```text
07c03ac2e051eded3873562d6e23c048e404571dbd7ec73d85770575f326a1df
```

## 加载与启动

需要 Root。将下载的模块推送到手机：

```sh
adb push vt_abi_probe.ko /data/local/tmp/vt_abi_probe.ko
adb shell
```

进入手机终端后执行：

```sh
su
cp /data/local/tmp/vt_abi_probe.ko /data/adb/vt_compat_4.9.186_v03.ko
chmod 600 /data/adb/vt_compat_4.9.186_v03.ko
insmod /data/adb/vt_compat_4.9.186_v03.ko
sh /data/adb/VT内核-4.7.7.sh
```

如模块已经加载，直接启动 VT，无需重复 `insmod`。v0.3 加载后会创建两个可见节点：

- `/dev/VTp03A`：供原版 VT 枚举识别的 6 位名称端点。
- `/dev/vt_abi_probe`：诊断和自测端点。

两者权限均为 `root:root 0600`。本项目没有配置开机自动加载，重启后需重新执行 `insmod`。

v0.4 改为原驱动的节点模型：6 位随机字母数字名端点（每次加载名称不同，不再固定为 `VTp03A`）+ `/dev/vt_abi_probe`。任一节点被打开后会立即从 `/dev` 消失，最后一个描述符关闭后按同一名称恢复，详见[隐藏逻辑](#隐藏逻辑v04)。

卸载前退出 VT 及其他使用该设备的程序，再在 Root 终端执行：

```sh
rmmod vt_abi_probe
```

如果模块仍被占用，先结束使用它的进程并等待文件描述符关闭。

**v0.4 默认 `hide_module=1`**：模块会把自己从内核模块链表移除，`rmmod` 返回 `ENOENT`，只能重启后重新加载。需要保留卸载能力时用下面的方式加载：

```sh
insmod /data/adb/vt_compat_4.9.186_v04.ko hide_module=0
```

## 真机验证结果

以下为 **v0.3** 的结果。v0.4 的隐藏逻辑尚未经过真机验证，其记录不得沿用本节结论。

2026-10-17，在原脚本未修改、未注入跟踪库的情况下，VT 输出：

```text
[+] VT驱动已安装，跳过自动刷入
```

同轮原生自测及加载、卸载检查结果：

```text
LOAD_STATUS=0
PASS: VT discovery handshake and self/child memory/module tests
SELFTEST_STATUS=0
ORIGINAL_VT_RECOGNIZED=1
CLEAN_UNLOAD_STATUS=0
FINAL_LOAD_STATUS=0
FINAL_LOADED_VERSION=0.3
```

测试覆盖精确的发现握手、自身和专用子进程的内存读写、父子内存隔离、子进程写入确认、自身与子进程的模块查询，以及无效 PID、长度上限、缺失模块和不支持命令的错误处理。

自行复测时，将 `vt_probe_test` 推送到手机；保持此文件名，以便模块查询测试匹配：

```sh
adb push vt_probe_test /data/local/tmp/vt_probe_test
adb shell
```

模块已加载后，在手机终端执行：

```sh
su
chmod 700 /data/local/tmp/vt_probe_test
/data/local/tmp/vt_probe_test
echo $?
```

预期出现上述 `PASS`，退出码为 `0`。

## 功能范围

| 功能 | 当前状态 |
| --- | --- |
| VT 4.7.7 设备发现与握手 | 真机通过 |
| 自身进程内存读写 | 已实现并自测 |
| 跨进程内存读写 | 已实现，专用子进程测试通过 |
| 模块基址查询 | 已实现，自身/子进程测试通过 |
| 6 位随机端点名（原 `get_rand_str`） | v0.4 已实现，待真机验证 |
| 设备节点打开后隐藏、关闭后恢复 | v0.4 已实现，待真机验证 |
| 模块从 `/proc/modules`、`/sys/module` 隐藏 | v0.4 已实现，待真机验证 |
| 硬件断点及命中查询 | 未实现，返回 `EOPNOTSUPP` |
| tracking | 未实现，返回 `EOPNOTSUPP` |
| 完整 PTE 接口 | 未完成 |
| 32 位兼容调用 | 不支持，返回 `EOPNOTSUPP` |

每次 ioctl 检查 `CAP_SYS_RAWIO`，单次内存操作上限为 **64 KiB**。跨进程访问通过 `/proc/<pid>/mem`，沿用调用者凭据及 procfs 的 ptrace/LSM 权限检查。模块查询读取 `/proc/<pid>/maps`，按文件名或完整路径匹配，返回首个匹配映射起始地址；未找到时返回基址 0。

## 隐藏逻辑（v0.4）

从内置第 7 份驱动的 `init_module`、`dispatch_open`、`dispatch_close` 和 `get_rand_str` 反汇编恢复，证据记录在 [protocol-evidence.json](protocol-analysis/protocol-evidence.json) 的 `hide_logic` 段：

| 阶段 | 原驱动行为 | 恢复依据 |
| --- | --- | --- |
| `init_module` | `get_rand_str` 用 62 字符表 + `get_random_bytes` 生成 6 位名称 | `get_rand_str` `0x334`，每字符一次 4 字节随机数 |
| `init_module` | `device_create` 发布节点 | `0x164` |
| `init_module` 末尾 | `list_del_init(&THIS_MODULE->list)` 后 `kobject_del(&THIS_MODULE->mkobj.kobj)` | `0x1b4`–`0x1cc` |
| `dispatch_open` | `device_destroy` + `class_destroy`，节点立即消失 | `0xb88`、`0xb90` |
| `dispatch_close` | `__class_create` + `device_create`，按同一 `dev_t` 与名称恢复 | `0xbe4`、`0xc2c` |

因此 v0.4：

- 每次加载生成不同的 6 位字母数字节点名，原程序仍按 6 位字母数字规则枚举到它。
- 节点被打开后不再出现在 `/dev`，VT 依靠已持有的描述符继续工作；最后一个描述符关闭后节点恢复。
- 模块不再出现在 `/proc/modules`、`lsmod`、`/sys/module`，kallsyms 的模块遍历也不再列出其符号。该步骤不可逆，`rmmod` 会失败，需要重启；测试迭代时用 `insmod ... hide_module=0`。
- 隐藏后不能再用 `lsmod` 判断是否已加载：请检查 `/dev/vt_abi_probe` 是否存在。重复 `insmod` 会在创建固定名诊断端点时撞上 `/sys/class/vt_abi_probe`，由内核以 `EEXIST` 拒绝（`insmod` 报 `File exists`），因此不会静默叠出多个实例。

只复刻了上述机制。原驱动中没有发现 `/proc` 过滤、系统调用挂钩或进程隐藏代码，本实现也没有添加。`list_del_init` 在原驱动中同样未持有 `module_mutex`，本实现与其一致，风险相同。

## 自动安装失败的定位

原程序先枚举 `/dev` 下的 6 位字母数字设备名，再发送读取命令 `0x02813449`，请求内容为：

```text
pid=-1, addr=0, buffer=0, size=0
```

它依赖该无效请求的错误码判断是否找到驱动。原驱动返回原始 `-1`，在用户态表现为 `EPERM`；v0.2 返回 `EINVAL`，因此被原程序排除。

v0.3 增加 6 位可见端点，并仅对这个精确的无效读取请求兼容 `EPERM`。此路径不访问内存，不返回伪造的读取成功。此次修复已使原版 VT 跳过自动刷入；未据此宣称原版自动安装器支持所有 4.9 内核。

## 协议与构建

协议证据来自 VT 4.7.7 内置第 7 份驱动（标记为 `4.14.117-perf+`）保留的 DWARF、函数名及重定位反汇编。离线检查已核对 **29 个字段偏移、5 个结构体大小、9 个命令号**。

| 原始命令号 | 接口 |
| --- | --- |
| `0x02813441` | 安装硬件断点 |
| `0x02813442` | 查询断点命中 |
| `0x02813443` | 启用硬件断点 |
| `0x02813444` | 清除全部硬件断点 |
| `0x02813445` | 禁用硬件断点 |
| `0x02813446` | 更新 tracking 数据 |
| `0x02813449` | 读取进程内存 |
| `0x02813450` | 写入进程内存 |
| `0x02813451` | 查询模块基址 |

这些是原始整数命令号，不使用 `_IOWR` 重新计算。该证据不证明所有内置驱动或主程序功能使用完全相同的协议。

### GitHub Actions

打开 [Build VT ABI diagnostic module for dipper 4.9](https://github.com/Ling-G/xiaomi8-sukisu-build/actions/workflows/build-vt-probe.yml)，点击 **Run workflow**，分支选择 **`vt-abi-probe-4.9`**。

构建使用固定版本源码、工具链和匹配配置，准备内核头文件与构建工具，再以外部模块方式生成 `.ko`，核对 ELF 架构、vermagic 和所有导入符号 CRC。此工作流不生成刷机镜像，不安装驱动。仅修改根目录 README 不会触发构建。

匹配依据：

- 内核源码：[MiCode / dipper-q-oss，dcfb167](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/dcfb1676925aec83b06ae04fd8ca989ced75067c)。
- 完整权威符号表：11,641 个导出符号，`module_layout` CRC 为 `0x2ee5b3bb`。
- 完整符号表 SHA256：`a5cac55aa1398925453e75aa82f527d8cdb2386b4242cdb05ab3312b651aad80`。
- 内核配置 SHA256：`cc904ba698d456659efb8eb85082e475c7e29142a4cf81dea3011d5b697faa9a`，与测试手机导出的配置一致。

### 本地构建

需要 Linux、与目标手机匹配且已准备好的内核构建目录、匹配的 `Module.symvers` 以及 AArch64 工具链。在仓库根目录执行：

```sh
python3 vt-prototype/verify_abi.py
make -C vt-prototype \
  KDIR=/absolute/path/to/matching/kernel-out \
  ARCH=arm64 \
  CROSS_COMPILE=/absolute/path/to/gcc64/bin/aarch64-linux-android-
```

单独运行 `modules_prepare` 不会生成匹配的完整 `Module.symvers`。

## 源码导航

| 路径 | 内容 |
| --- | --- |
| [vt-prototype/](vt-prototype/) | 外部模块、协议头、自测程序与校验脚本 |
| [protocol-analysis/protocol-evidence.json](protocol-analysis/protocol-evidence.json) | 协议布局与命令的分析证据 |
| [vt-prototype/build-actions.sh](vt-prototype/build-actions.sh) | 外部模块构建入口 |
| [.github/workflows/build-vt-probe.yml](.github/workflows/build-vt-probe.yml) | GitHub Actions 工作流 |
| [pins.json](pins.json) | 固定来源及工具链记录 |

根目录本文记录 v0.3 真机验证后的状态；子目录中的早期阶段说明若仍写有“待验证”，以本文的已验证版本和功能范围为准。

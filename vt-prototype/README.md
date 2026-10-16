# VT 通信接口诊断原型

状态：协议分析与最小源码已完成；尚未编译、加载或通过真机测试。它不是可直接替代 VT 的完整驱动。

## 已确认的证据

- 分析对象为从 VT 4.7.7 运行时数据提取的第 7 份驱动，内核版本标记为 `4.14.117-perf+`。
- 该驱动保留 DWARF 调试信息、函数名及重定位记录。`vt_protocol.h` 的字段偏移来自这些信息，命令号来自 `dispatch_ioctl` 的分发表。
- 手机当前内核为 `4.9.186-perf-g10af704`。手机导出的配置与用户提供目录中 `output/dipper-sukisu-bootstrap-late-candidate/kernel.config` 的 SHA256 均为 `cc904ba698d456659efb8eb85082e475c7e29142a4cf81dea3011d5b697faa9a`。
- 本地保存有小米源码压缩包，固定提交为 `dcfb1676925aec83b06ae04fd8ca989ced75067c`，以及 SukiSU/SUSFS 集成脚本。源码压缩包本身不等于完成集成并生成头文件的构建目录。
- 用户补充的 `images/Module.symvers` 与新生成的 `symvers-artifact/artifacts/Module.symvers` 完全相同，含 11,641 个导出符号，SHA256 为 `a5cac55aa1398925453e75aa82f527d8cdb2386b4242cdb05ab3312b651aad80`，`module_layout` CRC 为 `0x2ee5b3bb`。构建记录中的配置哈希与手机一致。较早音频/后台构建的同名文件不同，不能直接混用。

## 命令映射

| 命令号 | 原驱动处理入口 | 请求大小 |
| --- | --- | --- |
| `0x02813441` | 安装硬件断点 | 360 |
| `0x02813442` | 查询断点命中 | 32 |
| `0x02813443` | 启用硬件断点 | 360 |
| `0x02813444` | 清除全部硬件断点 | 无输入 |
| `0x02813445` | 禁用硬件断点 | 360 |
| `0x02813446` | 更新 tracking 数据 | 32 |
| `0x02813449` | 读取进程内存 | 32 |
| `0x02813450` | 写入进程内存 | 32 |
| `0x02813451` | 查询模块基址 | 24 |

这些是原始整数命令号，不应使用 `_IOWR` 重新计算。分发表中的其他槽位进入默认返回分支。这里只确认了该 4.14 驱动的接口，未证明全部内置驱动或所有主程序功能都使用相同协议。

## 原型范围

`vt_abi_probe.c` 使用固定、可见的 `/dev/vt_abi_probe` 端点，保留已确认的内存请求布局及读写命令号。它只允许对调用进程自身进行至多 64 KiB 的用户地址拷贝，每次调用检查 `CAP_SYS_RAWIO`，设备权限为 0600。

模块基址、跨进程读写、硬件断点和 tracking 尚未实现，对这些已知命令返回 `EOPNOTSUPP`，不伪造成功。错误路径使用标准 errno，并不逐条复刻原驱动的错误返回。没有实现原驱动中的模块隐藏或设备隐藏逻辑。

原 VT 主程序如何发现设备、是否接受该端点、是否在连接前校验驱动，以及 PTE 接口是否属于另一套协议，均尚未验证。不要把本原型描述为已经可以运行 VT。

## 验证与构建

`python3 verify_abi.py` 会从实际头文件声明计算布局，并与 `../protocol-analysis/protocol-evidence.json` 中的 DWARF 证据对照。它不需要手机，也不加载模块。

构建需要 Linux 环境、与当前手机一致且已准备好的内核构建目录及匹配的 `Module.symvers`，并使用原构建的 AArch64 GCC 工具链：

```sh
make KDIR=/absolute/path/to/matching/kernel-out \
     ARCH=arm64 CROSS_COMPILE=/absolute/path/to/gcc64/bin/aarch64-linux-android-
```

不能仅运行 `modules_prepare` 来替代生成匹配的 `Module.symvers`。`build-actions.sh` 已准备为 GitHub Actions 重建同一内核配置并编译原型，随后用 `verify_module.py` 核对 ELF 架构、vermagic 和所有导入符号 CRC；还会把导入 CRC 与用户提供的表格对照。构建是否通过须以实际运行结果为准。

`probe_client.py` 是构建并另行审核后才使用的接口测试程序，覆盖自身内存读写、目标进程限制、长度上限和错误命令。它尚未执行，不会自动安装模块。

后续需要：重建原集成内核并取得匹配构建输出；编译原型；审核模块依赖和版本；完成原型真机验证；继续分析主程序发现与连接流程。完整 VT 驱动还需要独立实现并验证余下功能。

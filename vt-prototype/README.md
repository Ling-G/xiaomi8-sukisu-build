# VT 通信接口诊断原型

状态：v0.3 已完成独立 `.ko` 编译、真机加载、自身和专用子进程读写、模块查询、卸载测试，并已通过原版 VT 4.7.7 的识别测试。v0.4 在此之上实现原驱动中的模块隐藏与设备隐藏逻辑，源码与离线校验已完成，尚待构建和真机验证。它还不是完整 VT 驱动。

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

`vt_abi_probe.c` 按原驱动的机制创建字符设备：`alloc_chrdev_region` + `cdev_add` + `__class_create` + `device_create`，共两个端点。该内核未启用 `CONFIG_DEVTMPFS`，`/dev` 节点由 Android ueventd 依据 uevent 创建，默认规则为字符设备 `root:root 0600`；这一点需在真机上用 `ls -l` 复核。

- 6 位随机字母数字名端点：名称在 `init_module` 中用 `get_random_bytes` 按原驱动的字符表和取模方式生成，供原程序枚举识别。
- `/dev/vt_abi_probe`：固定名称的诊断与自测端点。

两个端点共用同一处理函数。任一端点被打开时，其 class 与设备节点被销毁；最后一个描述符关闭后，按原 `dev_t` 与同一名称重新创建。这与原 `dispatch_open`/`dispatch_close` 的行为一致。

模块隐藏：`init_module` 末尾执行 `list_del_init(&THIS_MODULE->list)` 与 `kobject_del(&THIS_MODULE->mkobj.kobj)`，之后 `/proc/modules`、`lsmod`、`/sys/module/vt_abi_probe` 均不再出现该模块，kallsyms 的模块遍历也不再列出其符号。该操作不可逆，`rmmod` 会返回 `ENOENT`，需要重启才能卸载；测试迭代时用 `insmod vt_abi_probe.ko hide_module=0` 保持可卸载。

单次内存操作上限 64 KiB，每次调用检查 `CAP_SYS_RAWIO`。自身进程使用标准用户地址拷贝；其他进程通过 `/proc/<pid>/mem` 访问，打开文件时继续使用调用者凭据，接受 procfs 原有的 ptrace/LSM 检查。模块查询读取 `/proc/<pid>/maps`，返回第一个匹配文件名或完整路径的映射起始地址，未找到时基址为 0。

硬件断点和 tracking 尚未实现，对这些已知命令返回 `EOPNOTSUPP`，不伪造成功。错误路径使用标准 errno，并不逐条复刻原驱动的错误返回。隐藏逻辑只复刻上述四处机制；原驱动中没有找到 `/proc` 过滤、系统调用挂钩或进程隐藏代码。原驱动在执行 `list_del_init` 时不持有 `module_mutex`，本实现同样如此，风险与原驱动相同。

启动跟踪确认：原程序会打开 6 位节点，发送 `VT_MEMORY_READ`，请求体为 `pid=-1, addr=0, buffer=0, size=0`，以错误码识别设备。原驱动在此路径返回原始 -1，即用户态 `EPERM`；v0.2 的 `EINVAL` 导致候选被排除。v0.3 仅对这个精确的无效读取请求兼容 `EPERM`，不执行内存访问，也不伪造成功。原程序实际识别状态须以本轮未修改、无跟踪注入的启动测试为准，PTE/断点功能依然不能描述为已实现。

## 验证与构建

`python3 verify_abi.py` 会从实际头文件声明计算布局，并与 `../protocol-analysis/protocol-evidence.json` 中的 DWARF 证据对照；同时检查 `vt_abi_probe.c` 是否仍按恢复出的偏移实现隐藏步骤（随机名 6×62 字符表、`list_del_init`、`kobject_del`、`device_destroy`/`class_destroy`、`__class_create`/`device_create`），并核对证据中的地址。它不需要手机，也不加载模块。

构建需要 Linux 环境、与当前手机一致且已准备好的内核构建目录及匹配的 `Module.symvers`，并使用原构建的 AArch64 GCC 工具链：

```sh
make KDIR=/absolute/path/to/matching/kernel-out \
     ARCH=arm64 CROSS_COMPILE=/absolute/path/to/gcc64/bin/aarch64-linux-android-
```

不能仅运行 `modules_prepare` 来生成匹配的 `Module.symvers`。本次已有用户提供的权威符号表：`build-actions.sh` 沿用固定版本的内核集成脚本，准备与手机完全相同配置的头文件和构建工具，再将所需符号的 CRC 子集交给 modpost 编译外部模块。随后用 `verify_module.py` 核对 ELF 架构、vermagic 和所有导入符号 CRC；每个导入也必须存在于用户提供的表格记录中。子集不是完整内核符号表，构建是否通过须以实际运行结果为准。

`probe_client.py` 是可选的 Python 自测，覆盖自身内存读写、无效 PID、长度上限和错误命令。原生 AArch64 客户端 `probe_client.c` 还会创建专用子进程，核对跨进程读取、写入后的父子内存隔离、子进程对写入结果的确认，以及自身/子进程的模块基址查询。`vt_hold_test.c` 编译出的 `vt_hold_test` 只负责打开诊断端点并保持 5 秒，用于从 shell 观察节点在打开期间消失、关闭后恢复。三个程序都不自行安装模块。

后续需要：由 Actions 编译 v0.4，核对模块 SHA256、全部导入 CRC 与 vermagic，再在真机上按 `hide_module` 两种取值分别验证；之后才是硬件断点与 tracking 的独立实现。源码始终作为外部模块编译，不修改 main，不生成刷机镜像，不设置开机加载。

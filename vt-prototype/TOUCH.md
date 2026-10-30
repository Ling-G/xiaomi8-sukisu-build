# 屏幕点击接口

点击部分编译为独立的 **`vt_touch.ko`**，与 `vt_abi_probe.ko` 一起输出。它可以单独加载、卸载，不依赖 VT 主程序或内存接口；固定控制节点 `/dev/vt_touch`、模块及输入设备始终可见。

当前状态：源码已实现，等待 Actions 编译及真机验证；不能将驱动返回成功等同于 Android 已接收点击。

## 加载和测试

目标为小米 8，内核 `4.9.186-perf-g10af704`，原生竖屏 1080×2248。下载 Actions 产物中的 `vt_touch.ko` 和 `vt_touch_test`：

```sh
adb push vt_touch.ko vt_touch_test /data/local/tmp/
adb shell
su
insmod /data/local/tmp/vt_touch.ko
chmod 700 /data/local/tmp/vt_touch_test
/data/local/tmp/vt_touch_test --selftest
```

自测不产生有效点击，覆盖 ABI 查询、坐标越界、时长、保留字段、非法指针及未知命令，确认拒绝请求不增加计数。

把手机解锁，保持竖屏，将前台切换到可观察点击的测试页面，然后执行单次测试：

```sh
/data/local/tmp/vt_touch_test --tap 540 1124 80
```

程序倒计时 3 秒后，经 `/dev/vt_touch` 发送一次按下和抬起；`80` 表示按下持续 80 毫秒，允许 10–1000 毫秒。不调用 `input tap` 或 `sendevent`。请保持测试期间没有其他点击客户端，以便核对计数只增加 1。默认无参数等同 `--selftest`。

坐标原点为设备自然竖屏左上角，范围 X=0–1079、Y=0–2247；横屏和修改显示尺寸后的坐标需要调用方自行转换。驱动不查询 Android 当前旋转角度。可在加载时显式设置 `width=1080 height=2248`，允许尺寸 16–16384。

Android 需要先发现新增输入设备。用 `dumpsys input` 查找 `VT Touchscreen`，用 `getevent -lp` 确认对应 `/dev/input/eventN`。在另一个 Root 终端执行 `getevent -lt /dev/input/eventN`，再运行单次测试，应看到 tracking ID、坐标、同步、tracking ID=-1 和抬起同步。Android 点击效果另以测试页面收到的触摸事件确认。

退出客户端后可卸载：

```sh
rmmod vt_touch
```

未设置开机加载。重复加载会由正常模块管理拒绝；卸载会移除控制节点与输入设备。

## 接口

公共定义见 [`vt_touch_protocol.h`](vt_touch_protocol.h)，属于本项目扩展，不是逆向得到的原 VT 接口；原 VT 不会自动调用它。

| 命令 | 参数 | 说明 |
| --- | --- | --- |
| `VT_TOUCH_GET_INFO` / `0x80185401` | `struct vt_touch_info`，24 字节 | 返回 ABI=1、宽、高和已完成点击计数 |
| `VT_TOUCH_CLICK` / `0x40105402` | `struct vt_touch_click`，16 字节 | x/y/duration_ms/reserved，四个 uint32，reserved 必须为 0 |

每次调用检查 `CAP_SYS_RAWIO`；控制节点权限为 0600。仅支持原生 AArch64。非法参数返回 `EINVAL`，无效用户地址返回 `EFAULT`，未知命令返回 `ENOTTY`。点击同步完成后返回，计数代表已向 Linux 输入子系统提交完整按下/抬起，不代表 Android 应用已处理。

驱动创建名为 `VT Touchscreen` 的标准直接触屏设备，使用一个 Protocol B 多点触摸槽。完整点击由互斥锁串行执行，内核负责有界等待并抬起，不向调用方暴露容易遗留按住状态的单独 DOWN 接口。目前不支持滑动、多指、压力或物理触屏设备复用。

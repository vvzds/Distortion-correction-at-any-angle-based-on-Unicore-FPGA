# 功能、原理与操作

## 数据通路

OV5640 CMOS2 以 RAW8 输出，FPGA 恢复彩色并生成 RGB565。摄像头写入完整原始 DDR 帧槽后，校正引擎锁定可读帧。
引擎遍历输出坐标，先应用逆仿射（或姿态映射），再通过真实 Brown4 参数计算原图采样坐标，分块读取 DDR，取四邻域做 RGB565 双线性插值。校正帧写完并发布后，HDMI 读取它进行显示。
Gamma 在校正链路内处理亮度；降噪、锐化和文字叠加属于显示处理。实时视频始终更新，锁定姿态不等于冻结一张图片。

## 功能与实现位置

| 功能 | 实现及入口 |
|---|---|
| RAW8、DDR、HDMI | [顶层及相关 RTL](../../deliverables/20261103/resource_opt_shared32/source/rtl/) |
| Brown4 反向映射 | `brown_map.v`，参数由 `host/model.py` 编码 |
| 分块访存与插值 | `tile_engine.v`、`patch_store.v`、`bilinear_rgb.v` |
| 动态姿态补偿 | `bno085_bridge.v`、`imu_projective_map.v`，FPGA 内运行 |
| 自适应 Gamma | `adaptive_gamma.v` |
| 降噪、锐化、OSD | `display_denoise.v`、`display_sharpen.v`、`video_osd.v` |
| UART 与帧边界应用 | `host_control.v`、`feature_key_control.v`；协议见 [PROTOCOL](../../deliverables/20261103/resource_opt_shared32/PROTOCOL.md) |
| 电脑视觉参考锁定 | `host/board_trial.py` 和 `host/stabilizer.py`：电脑估计运动，FPGA 采样变换 |

## 板端按键

| 按键 | 作用 |
|---|---|
| KEY0 | Brown 畸变校正开/关；关闭 Brown 不等于旁路整条系统 |
| KEY1 | BNO085 姿态补偿开/关，开启时捕获当前有效姿态作为参考 |
| KEY2 | 自适应 Gamma 开/关 |
| KEY3 | Host → DN1 → DN1+SH1 → DN2+SH1 → Host |
| KEY4 | OSD 文字显示/隐藏 |

主机仿射参数在 KEY1 两种状态下都有效；主机画质命令接管后回到 Host 档。完整定义见[工程按键表](../../deliverables/20261103/resource_opt_shared32/KEY_FUNCTIONS_20261103.md)。

## 平移与转动的区别

BNO085 提供姿态/角速度，KEY1 的模型补偿相机转动，不提供场景平移估计。平移导致的画面移动并不说明仿射采样器失效。
现有电脑视觉程序用 ORB/LK、RANSAC 和固定参考，估计背景旋转及位移，再通过 UART 下发矩阵；几何像素处理仍由 FPGA 执行。它需要持续连接电脑、采集卡和串口。

在完整工程目录可运行已有视觉模式（设备释放、相机对准静态纹理背景后）：

```powershell
.venv\Scripts\python.exe -c "from host.protocol import Connection; c=Connection('COM8'); c.set_pose_map(False); c.close()"
.venv\Scripts\python.exe host/board_trial.py --port COM8 --camera 1 --zoom 1.5 --gamma
```

按 S 锁定、R 重锁、X 关闭、Q 退出；视觉模式不要再按 KEY1。这里复用工程已有程序，11 月 4 日本机启动确认不被算作新的运动效果验收。

1.5 倍裁切可给小位移留余量，视野会变窄。单个二维仿射无法消除所有深度视差、遮挡、运动模糊或移出视野的内容，也不能保证任意角度无黑边。不能用冻结视频替代稳像效果。

# 基于紫光同创 FPGA 的实时畸变校正与动态仿射系统

面向 2026 全国大学生嵌入式芯片与系统设计竞赛的 FPGA 图像处理工程。
硬件为盘古 100Pro+（MES2L676 / BASE V1.2、PG2L100H-6 FBG676）、OV5640 CMOS2 和可选 BNO085；使用紫光同创 PDS 2022.2-SP6.1。

**比赛提交请从 [提交入口](submission/README.md) 开始。** 最新收到的完整工程是 2026-11-04 Gamma 高光压缩 + KEY4 四行标定 OSD 候选，附件及逐文件清单校验通过，**尚未上板**。随包 PDS 路由证据的源码哈希与包内 4 个 RTL 文件不一致，因此该证据不能直接证明当前包内源码已通过布线；重新构建后再进行板测。11-03 位流保留为有快速板测记录的回退版本；两版结论不可混用。

| 要找的内容 | 入口 |
|---|---|
| 最新候选 ZIP、工程、位流和 SHA256 | [2026-11-04 候选说明](deliverables/20261104/README.md) |
| 最新完整 PDS 工程 | [gamma_highlight_key4_pkg676_final/pango_undistort.pds](deliverables/20261104/gamma_highlight_key4_pkg676_final/pango_undistort.pds) |
| 最新 FPGA 源码 / IP / 引脚约束 | [RTL](deliverables/20261104/gamma_highlight_key4_pkg676_final/source/rtl/) · [IP](deliverables/20261104/gamma_highlight_key4_pkg676_final/ipcore/) · [FDC](deliverables/20261104/gamma_highlight_key4_pkg676_final/HDMI_DDR3_OV5640_test.fdc) |
| 最新候选 SRAM 位流（尚未上板） | [FBG676 seed1](deliverables/20261104/gamma_highlight_key4_pkg676_final/bitstreams/pango_quality_gamma_highlight_key4_pkg676_seed1_20261104.sbit) |
| 最新上位机及标定参数 | [host](deliverables/20261104/gamma_highlight_key4_pkg676_final/host/) · [真实标定 JSON](deliverables/20261104/gamma_highlight_key4_pkg676_final/calibration/ov5640_1080p.json) |
| 已快速板测的回退位流 | [11-03 FBG676 seed1](deliverables/20261103/resource_opt_shared32/bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit) |
| 下载、运行、构建 | [快速开始](docs/submission/QUICKSTART.md) |
| 功能、按键和处理原理 | [系统说明](docs/submission/ARCHITECTURE.md) |
| 实测性能、资源及时序 | [验证汇总](docs/submission/VALIDATION.md) · [板测回执](submission/evidence/quick_board_test_20261103.md) |
| 开发阶段与历史版本 | [历程及版本导航](docs/submission/HISTORY.md) |

## 图像链路

```text
OV5640 RAW8 → 去马赛克 / RGB565 → 原始帧 DDR
    → 输出坐标反向映射（仿射 / Brown 畸变 / 可选姿态映射）
    → 分块 DDR 读取 → 双线性插值 → 可选自适应 Gamma
    → 校正帧 DDR → 显示降噪 / 锐化 / OSD → HDMI 1920×1080@30Hz
```

UART 用于标定和仿射参数配置、画质控制及状态回读。BNO085 姿态补偿可在 FPGA 内运行；基于画面跟踪的平移稳像需要电脑和采集卡持续参与。

## 验证状态

11-04 候选：29 项软件/RTL回归通过，UART坏 CRC 与忙状态补测通过。包内 PDS 报告记录 seed1 `All Constraints Met`、slow setup +0.378 ns、hold +0.138 ns；但对应源码哈希与当前包内 4 个 RTL 文件不符，不能将此时序结果作为当前源码的布线结论。**尚未下载到开发板**，需先对包内源码重新构建并核对新位流哈希，再进行板测。

11-03板测结果只适用于该版的位流 SHA `383daa2d…55d0`，不能作为11-04位流的板测证明。

| 项目 | 结果及口径 |
|---|---|
| 11-03已板测回退版 | 1920×1080；30秒窗口采集901帧 / 30.015秒，约30.018fps；UART发布约30.005次/秒 |
| 11-04随包PDS报告 | 记录 All Constraints Met；slow setup +0.378 ns、hold +0.138 ns；报告源码清单有4项与当前包内RTL不符 |
| 11-04最新候选资源 | LUT 24.4%、FF 17.5%、APM/DSP 43.3%、DRM 54.5% |
| 11-04软件/RTL回归 | 29项通过，另有UART坏CRC和忙状态的针对性回归通过 |
| 11-03板端功能 | Brown、Gamma、画质档位、OSD、BNO085姿态开关、主机小角度仿射快速检查通过 |

11-03板测是快速功能筛查；10分钟长稳未执行。姿态补偿不提供任意平移下的全景锁定，大角度或移出视野仍可能出现黑边。11-04候选没有板测。完整口径见[验证汇总](docs/submission/VALIDATION.md)。

11-04最新候选位流 SHA256（未上板）：

```text
e0f79c42eeec47798c46ac3e98c9c314bad2b0edf360b5fcb70be6b69a18db07
```

## 仓库布局与版本

`deliverables/20261104/gamma_highlight_key4_pkg676_final/` 是最新收到的候选；先按候选说明重建并验证源码/位流对应关系。`deliverables/20261103/resource_opt_shared32/` 是有快速板测记录的回退版本。两份工程独立保存，均有逐文件SHA256。
根目录的 `task1_1080p30.pds`、`source/`、`ipcore/` 和 `uart_host_tool/` 保留早期宿主/接口版本，属于开发历史。不同版本的位流、协议和板测回执不可互相替代。

仓库公开可读；直接写权限由 GitHub 协作者权限控制。源码来源与第三方 IP 说明见[来源说明](docs/submission/PROVENANCE.md)，本次整理不新增通用开源许可。

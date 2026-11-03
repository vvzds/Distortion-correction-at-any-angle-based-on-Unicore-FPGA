# 基于紫光同创 FPGA 的实时畸变校正与动态仿射系统

面向 2026 全国大学生嵌入式芯片与系统设计竞赛的 FPGA 图像处理工程。
硬件为盘古 100Pro+（MES2L676 / BASE V1.2、PG2L100H-6 FBG676）、OV5640 CMOS2 和可选 BNO085；使用紫光同创 PDS 2022.2-SP6.1。

**比赛提交请从 [提交入口](submission/README.md) 开始。** 当前演示基线为 2026-11-03 FBG676 seed1 完整工程，已完成快速功能板测。

| 要找的内容 | 入口 |
|---|---|
| 可直接下载的比赛整理包、完整工程和位流 | [Release 下载](https://github.com/vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA/releases/tag/competition-1080p30-20261104) |
| 完整 PDS 工程 | [deliverables/20261103/resource_opt_shared32/pango_undistort.pds](deliverables/20261103/resource_opt_shared32/pango_undistort.pds) |
| FPGA 源码 / 厂商 IP / 引脚约束 | [RTL](deliverables/20261103/resource_opt_shared32/source/rtl/) · [IP](deliverables/20261103/resource_opt_shared32/ipcore/) · [FDC](deliverables/20261103/resource_opt_shared32/HDMI_DDR3_OV5640_test.fdc) |
| 唯一推荐的演示位流 | [FBG676 seed1](deliverables/20261103/resource_opt_shared32/bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit) |
| 上位机及标定参数 | [host](deliverables/20261103/resource_opt_shared32/host/) · [真实标定 JSON](deliverables/20261103/resource_opt_shared32/calibration/ov5640_1080p.json) |
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

## 当前已验证结果

| 项目 | 结果及口径 |
|---|---|
| 输出画面 | 1920×1080；30 秒运动快筛采集 901 帧 / 30.015 秒，约 30.018 fps |
| 校正帧发布 | 同一短窗口 UART 发布约 30.005 次/秒；结合画面内容变化检查 |
| 125 MHz 时序 | PDS 报告 All Constraints Met；DDR PHY slow setup +0.206 ns、slow hold +0.141 ns |
| 主要资源 | LUT 24.1%、FF 17.5%、APM/DSP 43.3%、DRM 54.5% |
| 软件 / RTL 回归 | FBG676 快照既有 29 次仿真运行通过，保留日志与输入哈希 |
| 板端功能 | Brown、Gamma、画质档位、OSD、BNO085 姿态开关、主机小角度仿射快速检查通过 |

上述板测是快速功能筛查；10 分钟长稳尚未执行。姿态补偿不提供任意平移下的全景锁定，大角度或移出视野仍可能出现黑边。完整口径见[验证汇总](docs/submission/VALIDATION.md)。

推荐位流 SHA256：

```text
383daa2d21270eda53d94d79f05f464feb8bae2a4710288cd600f535355c55d0
```

## 仓库布局与版本

`submission/` 是本次提交清单、哈希核验及实板摘要；`docs/submission/` 是面向评审的说明；`deliverables/20261103/resource_opt_shared32/` 是可构建的演示工程。
根目录的 `task1_1080p30.pds`、`source/`、`ipcore/` 和 `uart_host_tool/` 保留早期宿主/接口版本，属于开发历史，**演示请使用上表完整工程**。早期参数协议不能与当前 CRC16 协议混用。

仓库公开可读；直接写权限由 GitHub 协作者权限控制。源码来源与第三方 IP 说明见[来源说明](docs/submission/PROVENANCE.md)，本次整理不新增通用开源许可。

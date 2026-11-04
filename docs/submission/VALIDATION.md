# 验证结果与适用范围

本页区分两个对象：11-03 已快速板测的回退位流 `383daa2d21270eda53d94d79f05f464feb8bae2a4710288cd600f535355c55d0`；以及 11-04 Gamma/KEY4 候选位流 `e0f79c42eeec47798c46ac3e98c9c314bad2b0edf360b5fcb70be6b69a18db07`。本次仓库整理没有重新编译、烧录或追加板测。

11-04 附件 ZIP 和 798 项文件校验清单一致，PDS 引用文件存在；但随包的 `key4_direct_display_seed1_source_hashes_20261104.json` 与当前工程的 `adaptive_gamma.v`、`gamma_tables.vh`、`host_control.v`、`video_osd.v` 四个文件哈希不同。因此随包时序报告的 `All Constraints Met`、slow setup +0.378 ns、hold +0.138 ns 只能作为相近构建的记录，**不能声称是当前 ZIP 源码的时序结果**。本机 PDS 可执行文件存在，但唯一发现的 `fabric_shell` license 已于 2026-11-03 到期；当前源码重建在 license 检查阶段停止，未进入综合或布线。11-04 位流尚未上板。

## 时序与资源

来源：[11-03原始资源报告](../../deliverables/20261103/resource_opt_shared32/RESOURCE_UTILIZATION_20261103.md)、[FBG676构建验证](../../deliverables/20261103/resource_opt_shared32/PACKAGE_FBG676_VERIFICATION_20261103.md)及其 `pds_evidence/` 原生报告。以下数据属于 11-03 回退版，不代表 11-04 候选。

| 项目 | Used / Available | 占用 |
|---|---:|---:|
| LUT | 16,020 / 66,600 | 24.1% |
| FF | 23,292 / 133,200 | 17.5% |
| APM（DSP/MAC） | 104 / 240 | 43.3% |
| DRM | 84.5 / 155 | 54.5% |
| 分布式 RAM | 110 / 19,900 | 0.6% |

125 MHz DDR PHY slow setup WNS +0.206 ns、slow hold WHS +0.141 ns，PDS 2022.2-SP6.1 seed1 报告 All Constraints Met。不同报告的打包资源分类有重叠，不能相加。该数据属于整机，不能归为单个模块的开销。

## 2026-11-04 Gamma/KEY4 候选

候选报告记载 LUT 16,261、FF 23,322、APM 104、DRM 84.5、分布式 RAM 110、IO 144；但由于上述 4 项源码哈希差异，这些路由/资源数值没有绑定到 ZIP 中的精确源码快照。重新构建并确认来源前，它们只作为随包报告值留档，不作为当前工程的签核数据。板端 Gamma 效果、HDMI画面、1080p30和KEY4显示均未验证。

## 软件和 RTL

FBG676 源码快照保留 29 次通过的仿真运行，套件 ID 为 `1793663314050972800`，索引见[verification_summary.json](../../deliverables/20261103/resource_opt_shared32/reports/verification_summary.json)。
覆盖映射、DDR 行为模型、帧边界配置、帧所有权、姿态映射、平滑、Gamma、画质及 OSD 等；输入哈希与日志保留。
留出照片数据缺失导致真实相机像质分析跳过；“软件回归通过”不含这项测量，也不等于实板通过。

## 2026-11-03 快速板测

来源：[回执](../../submission/evidence/quick_board_test_20261103.md)、[结构化结果](../../submission/evidence/board_result_20261103.json)、[HDMI 分析](../../submission/evidence/hdmi_30s.json)及[同步 UART 统计](../../submission/evidence/uart_hdmi_30s_mjpg.json)。

| 项目 | 结果 |
|---|---|
| 器件及下载 | PG2L100H，JTAG ID 0x00602899，SRAM done bit=1，未写 Flash |
| 工程一致性 | 完整工程 496 项清单、内外位流校验通过 |
| 有效图像窗口 | MJPG 1920×1080，901 帧 / 30.015 秒，约 30.018 fps |
| 校正帧发布率 | 同步窗口约 30.005 次/秒；与运动内容变化快筛结合 |
| 核心、写回、片块、UART | 采样未见故障/新增错误 |
| 功能操作 | KEY0、KEY1、KEY2、KEY3、KEY4、主机画质/OSD优先级、5°仿射及恢复通过快速检查；部分项目依赖用户现场确认 |
| 10 分钟连续长稳 | 未执行 |

视频容器时长、实际抓取墙钟时长、UART 窗口时长不是同一个量；分别保留原始记录，不把它们混为一个精确帧率。
原始视频与截图保留于本机板测证据包，本次 GitHub 紧凑证据只含报告、统计与媒体哈希。

## 不能直接延伸的结论

- UART 发布次数不是独立输入内容帧数；HDMI 刷新率也不单独证明每帧内容不同。
- 小角度动态映射通过不代表任意镜头移动不动、不出现黑边或完成长期稳像验收。
- 其他 G4/C50/C63、其他 seed、60Hz 支线的时序或板测不能替代本位流结果。
- 旧 MTF 报告基于其他图像状态/附件工程，没有与本次推荐位流同条件绑定，因此不将最高 MTF 数值直接列作本位流指标。
- 本整理未补测端到端硬件延迟、全部像质指标或官方验收项目。

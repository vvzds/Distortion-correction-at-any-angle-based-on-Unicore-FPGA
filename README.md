# FPGA 图像畸变校正工程：生产模式 4 宿主基线

当前仓库收录视频链路宿主工程，目标硬件为盘古 100 系列
PG2L100H FBG676、CMOS2 OV5640，开发环境为紫光同创 PDS 2022.2-SP6.1。
视频格式为 RAW8 采集、RGB565 存储、HDMI 1920×1080 @ 30Hz。

**当前边界：本版本的 `correction_hook.vh` 是空挂接点，尚未接入真实校正核。**
显示侧选择校正槽 4，必须有真实校正核写回并发布完整帧后才能出图；
直接构建和下载这个宿主版本，不能作为完整校正系统的显示演示。
本仓库也不等同于设计方的 G4 整机集成工程。

## 打开和构建

1. 使用 PDS 打开仓库根目录 `task1_1080p30.pds`。
2. 顶层为 `source/rtl/hdmi_ddr_ov5640_top.v` 中的 `hdmi_ddr_ov5640_top`。
3. 引脚与时序约束为 `HDMI_DDR3_OV5640_test.fdc`。
4. 可在 PowerShell 中运行 `./build.ps1 -PdsRoot '你的 PDS 安装目录'`。

`source/`、`ipcore/`、工程文件和构建脚本均应保留；构建输出由 `.gitignore`
排除。IP 目录中的源码、加密模型和初始化数据属于工程依赖，不能因其由
IP 工具生成而统一删除。厂商 IP 的使用以相应权利人的许可为准。

本次建仓没有更改 RTL、约束、IP 或冻结接口，也没有重新运行 PDS 或上板。
下文为原宿主包的构建记录与说明。

## Original host package notes

Source: `outputs/C1C5_顶行错位修复_20261014/旁路_1080p30_修复完整工程`.
The only RTL configuration change in this package is `VC_RD_SLOT_BASE=3'd4`
in `source/rtl/video_contract.vh`. The 2026-10-14 DDR read-completion
row-fix remains included. Target: Pango PG2L100H FBG676, PDS 2022.2-SP6.1,
CMOS2 OV5640 RAW8 capture and HDMI 1080p30 output.

Open `task1_1080p30.pds` in PDS. The top module is
`hdmi_ddr_ov5640_top` in `source/rtl/hdmi_ddr_ov5640_top.v`.
`HDMI_DDR3_OV5640_test.fdc` contains the corresponding board pin and timing
constraints and is referenced by the PDS project and `build.tcl`.

`source/rtl/correction_hook.vh` is an idle **production mounting point**.
It does not instantiate a distortion correction algorithm, request source
frames, write corrected pixels, or publish a corrected frame. With slot 4
selected, the host can compile but the display remains black until a real
correction core is connected through this hook and publishes a complete frame.
No bitstream is supplied or claimed to be board-validated for this mode.
Do not substitute the identity-copy test hook as a production correction core.

The package carries RTL, IP sources, the PDS project, build scripts and FDC.
Generated compile files, reports and old bitstreams are intentionally omitted.

Build check on 2026-10-18: PDS 2022.2-SP6.1 completed compile, synthesis,
device mapping, place and route, timing analysis, and bitstream generation.
The timing report states `Design Summary : All Constraints Met.` This checks
the host project's buildability; it is not a correction-function or board test.

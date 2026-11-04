# 2026-11-04 Gamma/KEY4 候选工程

本目录保存用户提供的最终工程 ZIP 和完整展开副本。上传后的压缩包名称为 `pango_gamma_key4_20261104.zip`，SHA256：

[下载完整工程 ZIP：pango_gamma_key4_20261104.zip](pango_gamma_key4_20261104.zip)

```text
43ffce9d221e4c9fd87561d0452e40696046fbbe37b7b84608fe9a6030a002f8
```

推荐位流文件为 `gamma_highlight_key4_pkg676_final/bitstreams/pango_quality_gamma_highlight_key4_pkg676_seed1_20261104.sbit`，SHA256：

```text
e0f79c42eeec47798c46ac3e98c9c314bad2b0edf360b5fcb70be6b69a18db07
```

## 状态

- 附件 ZIP 与 SHA256 一致；包内 798 项文件清单全部匹配，PDS 的 122 个 RTL、IP 和约束引用均存在。
- 保存的 29 项软件/RTL回归通过，另有 UART 坏 CRC 和忙状态补测记录。
- 包内 PDS seed1 路由收据报告 `All Constraints Met`、slow setup +0.378 ns、hold +0.138 ns。
- 路由源码哈希清单与当前 ZIP 中的 `source/rtl/adaptive_gamma.v`、`gamma_tables.vh`、`host_control.v`、`video_osd.v` 四个文件不同。因此现有时序证据**没有证明这份 ZIP 的精确源码通过该路由**。
- 此位流尚未上板。不可使用 11-03 回退版板测结果替代。

请先在 PDS 2022.2-SP6.1 对该目录完整构建，保存新构建输入哈希、时序报告及位流 SHA256，然后再烧录 SRAM 并验证摄像头、HDMI、1080p30、KEY4 OSD 和 Gamma 高光效果。本机有 PDS，但当前唯一发现的 `fabric_shell` license 已于 2026-11-03 到期；构建在 license 检查阶段停止，尚未综合或布线。

运行只读核验：

```powershell
python submission/verify_final_candidate.py
```

11-03 已快速板测工程仍在 `../20261103/resource_opt_shared32/`，其证据只适用于旧位流 `383daa2d...55d0`。

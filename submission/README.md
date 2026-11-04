# 比赛提交清单 · 2026-11-04

当前保留两个明确区分的版本：最新收到的 **2026-11-04 Gamma 高光压缩 + KEY4 标定 OSD 候选**，以及已有快速板测记录的 **2026-11-03 FBG676 seed1 回退版本**。11-04 候选尚未上板；其包内 PDS 路由源码清单与当前包内 4 个 RTL 文件哈希不一致，必须重新构建后才能把时序报告绑定到这份源码。

## 推荐交付

| 用途 | 文件 |
|---|---|
| 最新完整候选工程和原始附件 ZIP | [2026-11-04 候选说明](../deliverables/20261104/README.md) |
| 最新候选位流（源码对应关系待重建核实，尚未上板） | [FBG676 seed1](../deliverables/20261104/gamma_highlight_key4_pkg676_final/bitstreams/pango_quality_gamma_highlight_key4_pkg676_seed1_20261104.sbit) |
| 11-03 已快速板测回退工程及位流 | [完整工程](../deliverables/20261103/resource_opt_shared32/README.md) · [回退位流](../deliverables/20261103/resource_opt_shared32/bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit) · [板测回执](evidence/quick_board_test_20261103.md) |
| 候选重建受阻记录 | [license 检查回执](evidence/final_candidate_rebuild_attempt_20261104.json) |
| 11-03 旧版归档核验 | [旧版 manifest](manifest.json) · [旧版 SHA256](SHA256SUMS.txt) · [旧版只读校验器](verify_submission.py) |

11-04 原始工程 ZIP SHA256：`43ffce9d221e4c9fd87561d0452e40696046fbbe37b7b84608fe9a6030a002f8`。其中候选位流 SHA256：`e0f79c42eeec47798c46ac3e98c9c314bad2b0edf360b5fcb70be6b69a18db07`。位流尚未上板，不能据随包路由报告认定当前包内源码已通过布线。

11-03 回退位流 SHA256：`383daa2d21270eda53d94d79f05f464feb8bae2a4710288cd600f535355c55d0`；对应快速功能板测，不代表 11-04 候选结果。

## 最快的核对方法

在仓库根目录执行：

```powershell
python submission/verify_final_candidate.py
```

新校验脚本只读检查 11-04 ZIP、798 项文件清单、PDS 引用及构建源码哈希对应关系，不访问硬件、不编译或烧录。旧版可单独运行 `python submission/verify_submission.py`；它检查 11-03 已板测版本。
如果只拿到整理 ZIP，请将它完整解压到较短英文目录，例如 `D:\fpga_submit`，再执行 `python verify_package.py`。

## 实际使用

见[快速开始](../docs/submission/QUICKSTART.md)。默认单目 CMOS2；当前目标是 1080p30。KEY1 为姿态补偿，不能描述为支持任意平移的稳像。电脑视觉补偿是可选运行方式，见[系统说明](../docs/submission/ARCHITECTURE.md)。

## 证据与历史

`evidence/` 保留 11 月 3 日快速板测回执、结构化结果和短窗口统计；原视频/截图的 SHA 与本机来源仍记录在原始结果中。本整理包不重复加入现场长录像。
11-04 工程中的板测步骤仅为待执行流程，不能作为已完成的验收。`deliverables/` 的其他日期、其他 seed 与失败候选作为历史档案保留，不能替代各版本哈希绑定的结果。

# 比赛提交清单 · 2026-11-04

当前选择：**FBG676 seed1、1920×1080@30、真实 Brown 标定、功能键及画质集成版本**。
本次整理基于源码提交 `a3a2e92811567472af5b25274ed3e9d38ee5e2a1`，对应 2026-11-03 已快速板测的位流。

## 推荐交付

| 用途 | 文件 |
|---|---|
| 一份包含源码、完整工程、位流、说明和紧凑板测证据的整理包 | [比赛整理包](https://github.com/vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA/releases/tag/competition-1080p30-20261104) 中的 `FPGA_Competition_Submission_20261104.zip` |
| 保持原始字节的完整工程包 | [原工程 ZIP](../deliverables/20261103/resource_opt_shared32/pango_quality_function_keys_pkg676_full_20261103.zip) |
| 开发板 SRAM 下载 | [推荐位流](../deliverables/20261103/resource_opt_shared32/bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit) |
| 内容与结果核对 | [manifest.json](manifest.json) · [SHA256SUMS.txt](SHA256SUMS.txt) · [板测回执](evidence/quick_board_test_20261103.md) |

完整工程 ZIP 的 SHA256 为 `6b542ea0afb3c108983ecd716f89b3d21b82644aa79d07df7368a58afa637959`。
位流 SHA256 为 `383daa2d21270eda53d94d79f05f464feb8bae2a4710288cd600f535355c55d0`。提交包以最终发布的 Release 附件哈希为准。

## 最快的核对方法

在仓库根目录执行：

```powershell
python submission/verify_submission.py
```

脚本只读取文件，检查推荐资产、原工程 496 项清单、PDS 源文件/IP/约束引用和软件回归输入哈希，不访问硬件、不编译或烧录。
如果只拿到整理 ZIP，请将它完整解压到较短英文目录，例如 `D:\fpga_submit`，再执行 `python verify_package.py`。

## 实际使用

见[快速开始](../docs/submission/QUICKSTART.md)。默认单目 CMOS2；当前目标是 1080p30。KEY1 为姿态补偿，不能描述为支持任意平移的稳像。电脑视觉补偿是可选运行方式，见[系统说明](../docs/submission/ARCHITECTURE.md)。

## 证据与历史

`evidence/` 保留 11 月 3 日快速板测回执、结构化结果和短窗口统计；原视频/截图的 SHA 与本机来源仍记录在原始结果中。本整理包不重复加入现场长录像。
工程内旧报告所写“待板测”是报告生成时的状态，后续进展由本目录 11 月 3 日板测回执补充，原报告保持原样。
`deliverables/` 的其他日期、其他 seed 与失败候选作为历史档案保留，不能替代本清单推荐位流。

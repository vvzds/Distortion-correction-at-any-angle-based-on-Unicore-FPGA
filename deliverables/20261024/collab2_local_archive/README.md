# 项目本机资料全量归档（二号）

接收方：管理方/执行者、一号协作者、二号协作者。

本归档汇总本机已知项目目录，包含工程、RTL/IP、约束、位流、参数、标定原图、采集视频、原始交接包、仿真与物理证据，以及本机工具脚本。

## 完整性与去重

- 文件路径：188,336；不重复文件内容：14,518。
- 原始文件合计：30,094,477,580 字节；新增归档载荷：2,862,028,868 字节。
- 复用仓库已有内容：754 份，含G7/G8原始分片包。
- 所有对象已完整解码并检查 SHA256/长度；复用的Git对象已与本地原始字节比对Git blob哈希。见 VERIFICATION.json。
- ZIP字节、旧报告和旧参数原样保留；没有重新压缩原件后冒充原哈希。
- 软件安装器、依赖运行时缓存、Git登录配置/令牌、无关个人资料不入库；排除项见 filtered_exclusions.json。

## 当前入口与版本规则

- [当前G4静态校正整机候选](../collab2_G4_static_timing_pass/README.md)：1080p30、DDR125MHz，WNS +0.183ns；尚未板测。
- [按显式版本号排列的全部版本索引](VERSION_INDEX.json)：同一文件族优先较高版本，较低版本保持可恢复。
- 同版本、不同哈希的文件保留为并行候选；G4/G6/G8算法、门禁和生产整机属于不同工作线，不能仅按数字大小互相替换。
- 已合并管理方主线、一号资料分支、二号仓库接入与G4时序交付分支；原分支和提交保留。
- 主工程根目录的RTL/IP/FDC不因资料同步被混合替换；新增候选通过明确的版本入口提供。
- 历史失败报告、合成测试数据、软件候选与实机验收证据各按原路径保留，不把历史失败认作当前通过，也不把仿真/时序通过认作板测通过。

## 查找和恢复

无需第三方Python包。先在仓库根目录运行：

```powershell
python deliverables/20261024/collab2_local_archive/restore_archive.py --list
```

恢复桌面某次任务（替换为 --list 中的任务目录）：

```powershell
python deliverables/20261024/collab2_local_archive/restore_archive.py --root desktop_yx --prefix "G8_自动门禁与执行检查工具_20261023" --destination "D:/FPGA_restore"
```

恢复原D盘工程：

```powershell
python deliverables/20261024/collab2_local_archive/restore_archive.py --root pds_yx --prefix "static_G4_timing_resume_20261024/seed_4_hold20_r5" --destination "D:/FPGA_restore"
```

- 仅下载本目录ZIP分片不等于完整恢复；需同时保留 MANIFEST.json、PATHS.jsonl.gz 和工具引用的已有仓库对象。
- 需要普通 Git 访问已有对象；部分克隆可在需要时按Git对象取回。恢复工具默认不覆盖不同内容的已有文件。
- 恢复到同名工程目录并校验哈希后，再按对应工程SOP操作；不能混用不同候选的位流和参数。

## 本机目录覆盖

| 根标签 | 文件数 |
|---|---:|
| calibration_photo | 162 |
| codex_2026-09-17_wo | 2 |
| codex_a1024m01_M01 | 19 |
| desktop_FPGA | 5 |
| desktop_project_docs | 8 |
| desktop_yx | 41,498 |
| downloads_project | 6 |
| original_project_videos | 7 |
| pds_fpgaled | 16 |
| pds_last | 9 |
| pds_resouce | 3,639 |
| pds_sty | 5,413 |
| pds_ww | 8 |
| pds_yx | 3,229 |
| wechat_attach | 17 |
| wechat_file_2026-10 | 134 |
| workspace | 134,164 |

PATHS.jsonl.gz 保存每个原始绝对路径、根标签、相对路径、大小、时间戳和SHA256。ORIGINAL_IMAGES.json 另记本机仍存在的原始附件图；已不在本机的历史临时图片仅记录缺失，不伪造。


## 快速入口

- [按任务目录查找](TASK_INDEX.md)
- [补充的M01完整源码](supplemental_M01_sources.zip)；其335个补充源文件与报告生成脚本的原路径和单独校验见 SUPPLEMENTAL_FILES.json。
- [本机仍存在的项目原始附件图](ORIGINAL_IMAGES.json)；桌面独立旧位流与G6原说明在 standalone_project_files。
- 本地下载完成后运行 `python verify_downloaded_archive.py` 核验全部新增归档文件；完整逐对象解码证据见 VERIFICATION.json。

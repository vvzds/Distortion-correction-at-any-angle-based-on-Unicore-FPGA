# FPGA本机磁盘清理结果

制作：二号协作者；接收：用户、执行者/管理方；一号无需重新编译或提交回执。

已删除 2895 个文件，文件逻辑大小合计 **10.32 GiB**。本次清理的是磁盘空间，不是运行内存。

磁盘可用空间变化还受其他程序写入、文件系统压缩及分配单元影响，以下同时记录文件合计和实际可用空间。

| 磁盘 | 清理前可用GiB | 清理后可用GiB | 净增加GiB |
|---|---:|---:|---:|
| C | 18.15 | 24.95 | 6.80 |
| D | 40.74 | 41.62 | 0.88 |

## 已清理范围

| 原目录或文件 | 已删除文件数 | 合计GiB |
|---|---:|---:|
| `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\G8_receipt_review_20261024\delivery` | 225 | 0.205 |
| `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\V204_intake_independent_20261023\received` | 8 | 0.748 |
| `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\G6_PAP_GROUP_review_20261023\archive_cli_replay` | 142 | 1.078 |
| `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\G6_PAP_GROUP_review_20261023\G6_PAP_GROUP_binding_audit` | 141 | 1.078 |
| `D:\FPGA PDS\yx\static_G4_bringup_20261024` | 203 | 0.092 |
| `D:\FPGA PDS\yx\static_G4_timing_resume_20261024` | 2065 | 0.781 |
| `C:\Users\叶翔\Desktop\yx\本机项目全量归档上传_二号_20261024\完整归档` | 109 | 2.694 |
| `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\pds_sp64_setup\Setup.exe` | 1 | 1.821 |
| `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\pds_sp64_setup\payload_extract_only.nsis` | 1 | 1.821 |

## 保留和跳过

- 当前静态矫正完整工程 D:\FPGA PDS\yx\DCSjingtaijiaozheng 保留；当前位流SHA256仍为 `67ce6939f03abe9e9594f6bd071a567988eeda96fecb4eec2c3f5b8ed6cdf317`。
- 自适应Gamma候选、标定照片和参数、软件安装目录、官方配套资料、其他协作者工程及旧双目功能工程保留。
- 仓库本地全量归档及GitHub历史版本保留，删除桌面重复归档不影响历史版本恢复。
- 两份SP6.4文件仅为未使用安装介质，按冗余安装文件删除；安装好的PDS未修改。
- 计划阶段跳过 7 个目录；删除阶段跳过或失败 0 个文件，详见plan.json和deletion_journal.jsonl。
- 跳过 `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\G7_R01_R14_followup_20261023\delivery`：not fully backed up or changed。
- 跳过 `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\AB_M01_intake_compare_20261023\received`：not fully backed up or changed。
- 跳过 `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\outsourced_audit_20261024\received`：local recovery not fully verified; retained whole directory。
- 跳过 `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\G8_receipt_review_20261024\received`：local recovery not fully verified; retained whole directory。
- 跳过 `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\outsourced_audit_20261024\delivery`：local recovery not fully verified; retained whole directory。
- 跳过 `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\G7_R01_R14_followup_20261023\release`：local recovery not fully verified; retained whole directory。
- 跳过 `C:\Users\叶翔\Documents\Codex\2026-10-10\x20\work\G7_R01_R14_followup_20261023\received`：local recovery not fully verified; retained whole directory。

## 历史文件恢复

保留归档位于：
`C:\Users\叶翔\Documents\Codex\fpga-main\deliverables\20261024\collab2_local_archive`

执行清理前已逐文件比对SHA256，并通过解码归档对象或核对清单以外保留的等价文件验证恢复来源；recovery_verification.json包含检查结果、保留副本位置和计划哈希。无法在本机完成恢复验证的目录整目录保留，不依赖尚未下载的Git对象删除唯一资料。
plan.json的每条记录提供原路径、SHA256、archive.root及archive.rel。用仓库内restore_archive.py按指定root和prefix恢复到原根目录或新目录；完整参数见下例。不要直接把历史文件覆盖到正在用的工程。

```powershell
python "C:\Users\叶翔\Documents\Codex\fpga-main\deliverables\20261024\collab2_local_archive\restore_archive.py" --repo "C:\Users\叶翔\Documents\Codex\fpga-main" --git "C:\Users\叶翔\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe" --root pds_yx --prefix static_G4_timing_resume_20261024 --destination "D:\FPGA_restore"
```

桌面重复归档可从保留的仓库目录重新复制。无用安装介质未作备份，未来如确需安装，应从官方渠道重新取得。

## 证据文件

- plan.json：逐文件计划、备份引用及跳过原因。
- deletion_journal.jsonl：真实逐文件删除结果。
- recovery_verification.json：归档可恢复性验证。
- cleanup_result.json：文件合计和清理前后磁盘空间。
- scripts/：本轮盘点、验证和删除脚本，删除脚本存在已有执行日志时拒绝直接重跑。

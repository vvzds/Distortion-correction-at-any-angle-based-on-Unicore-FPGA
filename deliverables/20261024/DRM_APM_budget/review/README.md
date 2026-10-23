# DRM/APM资源预算审查包

先读DRM_APM资源预算审查报告_20261024.md，再读对应协作者的增量任务单。resource_ledger.csv为34份原生报告账本，resource_audit.json含逐模块层级/行号/分项一致性，source_index.json给原位置与SHA，evidence保留完整原生报告及引用规格/RTL。

复核不需PDS。运行 `python -B verify_review.py` 校验包内容。audit_resources.py保留本机原始提取入口（本机绝对路径仅用于追溯）；portable_recheck.py仅用包内evidence重新核查原生数字及账本，不需要访问管理方D盘或安装PDS。首次完整抽取的输入结束SHA不变，未进行新综合/P&R/板测。

仅DRM/APM数量/用途分项通过；cache16>12、LUT两表差异、时序/电气保持开放，当前AB新哈希资源待A01。总说明/正式任务表v2.0.4保持不变，本轮先记待汇总进展。

本次工作主要由 GPT-6 模型完成。

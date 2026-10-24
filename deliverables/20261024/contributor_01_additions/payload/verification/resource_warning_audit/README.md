# 一号协作者：A01–A03 资源与告警审查回传

本包给管理方/设计方接收，同时给二号协作者 B04 交叉复核；告警拓扑还请二号 B02 审阅。一包同发，无需拆散源码、日志或结果。未发送外部消息。

本轮已完成可独立推进的离线审验。A+B单seed2流程结束，但125MHz时序失败；G8历史8轮保持失败。没有生产提升、没有生成新位流或烧录，G4上板暂停保持。

先读：
1. reports/A01_AB单seed物理诊断与四层资源账本.md：A+B WNS−2.585ns，瓶颈在cache qid→last_use，资源两表一致，UART自动bank分配冲突。
2. reports/A02_工具交叉审验与历史执行适配.md：原工具/隔离适配器测试及严格4/8有效、0/8闭合结果。
3. reports/A03_共享仿真与资源复核.md：六帧零差异与性能口径，不替代物理通过。
4. reports/CW_告警清理与SCCB审查.md：最小清理结果、原生时钟/例外和未关闭项。
5. reports/统一待补材料与接收人.md、receipts.json：逐项范围、结果、接收方。

## 目录与身份

- runs/ab_seed2_inputs：本轮完整A+B离线输入和原生compile/syn/map/pnr/timing成果，无sbit。
- runs/cw_cleanup_seed2：独立G8宿主清理候选及完整原生结果；不能作为冻结G8、G4或上板工程。
- evidence：原始进程回执/全部console、失败启动尝试、软件自测、派生复核、原生实例账本；raw receipt不回写。
- reused_synthesis：2026-10-23匹配新AB core的原综合证据，标ORIGINAL_RUN_REUSED；不得把日期改成本轮。
- tools/tools：只读审查脚本及原门禁辅助模块；tools/tests为测试；tools/prepared_inputs为原147×8冻结夹具。
- tools/sccb_sim：源RTL及定向TB，入口run_portable.py；evidence/sccb_sim_final是最终相位3/47/93实跑。
- reference：精确输入归档索引、任务原件、厂商硬件资料及原FDC。

runs/cw_cleanup_seed2中的trial_inputs_sha256.json、run_trial.tcl是复制保留的冻结基线原文件；前者描述变更前输入，后者原本含gen_bit_stream。**此次实际候选身份必须使用cw_cleanup_evidence/inputs_before.json和清理diff，实际入口是cleanup_analysis.tcl**。未改写旧manifest冒充新候选，未执行原run_trial.tcl。相同原则适用于保留的历史build/impl入口；请先看执行回执。

AB wrapper的changed_input_files只有run.log，是早先启动失败产生的工具日志，被正式运行替换；RTL/FDC/IP/Tcl均未变。补充审计提供工具after SHA和原生版本确认，不篡改raw receipt中version_confirmed=false的原值。

## 已交大原件的可移机引用

原1.5GB输入不重复复制，reference/reused_archive_index.json提供外层完整SHA、archives子包完整SHA及路径。用原包prepare.py提取COMPARE/G8_RESULTS/G8_TOOLS等，在以下命令传入实际根目录；无需原作者D盘。

派生G8报告的source_path均相对G8_RESULTS根；共享仿真相对COMPARE/AB_G8_M01_review_20261023；原告警台账相对外层critical_warning_review。AB_independent_20261023/core来源对应本包reused_synthesis/core，其SHA相同。旧宿主source/IP与runs/ab_seed2_inputs字节相同，原compile/synthesize另附于reused_synthesis/host。输入比对表已列完整SHA，不用文件名替代身份。

## 复核入口（Python标准库；不会运行PDS）

在本包根目录运行，OUT使用不存在的新目录：

```powershell
python -B -X utf8 verify_delivery.py
python -B -X utf8 tools/tools/run_selftests.py --out OUT/selftests
python -B -X utf8 tools/tests/test_adapter.py
python -B -O -X utf8 tools/tests/test_adapter.py
python -B -X utf8 tools/tools/g8_preflight.py --inputs tools/prepared_inputs --out OUT/preflight
python -B -X utf8 tools/tools/management_adapter.py --results <已提取G8_RESULTS> --out OUT/derived --console-policy strict
python -B -X utf8 tools/tools/review_native_run.py --run runs/ab_seed2_inputs --out OUT/ab --label AB_OFFLINE
python -B -X utf8 tools/tools/review_native_run.py --run runs/cw_cleanup_seed2 --out OUT/cw --label CW_CLEANUP
python -B -X utf8 tools/tools/native_connectivity.py --warning-root <原包critical_warning_review> --out OUT/connectivity
python -B -X utf8 tools/sccb_sim/run_portable.py --tool-root <iverilog的app目录> --out OUT/sccb
```

PDS重现只供B04需要时使用：原prepare_ab_analysis.py新建隔离输入，Windows短盘符须与PDS在同一执行会话绑定，使用-file Q:/analysis.tcl -work_dir Q:/ -project_name ab_seed2_analysis。不要在已交原始成果目录复跑覆盖文件，不默认再跑八种子。工具SHA、实际版本、启动/结束、PID、超时、输入前后哈希都在原回执。

“PASSED_SCOPE”只表示该审查/验证范围通过；A+B/G8物理失败、电气缺证、原语级复位验证、接口/生产裁定分别保留。

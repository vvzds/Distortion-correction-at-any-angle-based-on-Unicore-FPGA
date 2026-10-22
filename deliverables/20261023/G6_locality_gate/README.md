# locality 自动门禁适配候选（2026-10-23）

本机已实现并执行独立候选 `startup-db-v1`；原 `D:/g6_locality_pkg`、原运行目录及生产源码未覆盖。该候选只解决启动阶段两条特定 E 行的自动分类，未解决绑定、时序闭合或整模块验收。

## 实际结果

| 检查 | 结果 |
|---|---|
| 原工具 / 候选默认 strict | 均 valid=0，拒绝 E 行 |
| 显式 startup-db-v1 | 8/8 单轮回执、输入/产物哈希、控制台及报告检查通过 |
| 时序 | 闭合 seed 5/7，2/8=25%，S1=false；S2=true |
| 绑定 / 物理门禁 | binding_confirmed=false；physical_trial_pass=false；collect 退出码仍为 2 |
| S5 | 本机完整运行目录的单轮证据项 complete=true；不代表本交付 ZIP 是可迁移的完整物理 S5 包 |
| S3/S4/整体 | 保留原工具 UNRESOLVED / PENDING / NOT DECLARED |
| 测试 | 普通模式 84/84；Python -O 84/84，均 PASS |
| 中断 seed 3 | 缺 PNR 成功及完整终点链，仍拒绝；无完成回执 |

`valid=8` 只表示本候选明示的单轮证据范围通过，不能写成 G6 正式验收通过或绑定已确认。未重新运行 PDS、仿真或上板。

## 适配依据和限制

8 轮原始日志第 3、4 行均为：

```text
E: Please rerun to generate compile db.
E: Flow-0011: PNR or PLC design DB file is not found.
```

其前面必须是 SP6.4 的许可证启动行和 `Compiling architecture definition.`，后面必须紧接本种子工程分析行及既定器件的 set_arch 命令。两条消息必须各一次、精确匹配，后续任何新增 E/ERROR/** Error/** Fatal 仍拒绝。不能全局删除或忽略 E 行。

消息发生在工程分析前，**不是 dev_map 后 export_fdc 失败的两条错误**。后者实际为 `W: Flow-4055` 和 `G6_EXPORT_UNAVAILABLE=`，仍原样保留，绑定问题独立未闭环。当前依据为可观察阶段链和产物证据，不声称已取得厂商对启动消息内部成因的正式认定。

启用适配前仍逐项执行原有退出码、种子、输入不漂移、全部回执产物哈希、必需文件非空且唯一、XML、原生 CSV 版本及终点四象限解析检查。随后要求 compile、synthesize、dev_map、PNR、report_timing、gen_bit_stream 成功记录及三个 G6_PHASE 标志各一次并按顺序出现；FINISHED 后不允许其他非空输出。回执还须标识既定 SP6.4 shell 路径。

策略只覆盖这一已观察到的日志格式；其他版本、启动格式或阶段输出须重新核查，不能扩大白名单以追求 PASS。回执哈希提供相对留档的一致性，不是对恶意重写整条回执链的数字签名认证。S1/S2 数值、绑定逻辑和 S3/S4/包级 S5 判据未修改。

## 使用

将本目录解压到独立目录，Python 3.10+ 标准库即可。两个 Python 文件 `pds_review.py` 与 `startup_console_gate.py` 须放在同一目录。

```powershell
python -B test_startup_console_gate.py
python -B -O test_startup_console_gate.py
python -B pds_review.py collect --run D:/g6_locality_runs_20261022 --console-policy startup-db-v1 --output D:/FPGA_management/evidence/locality_adapted_review_new.json
```

输出路径必须是尚不存在、位于原运行目录以外的文件。省略 `--console-policy` 即原有 strict；`--output` 现在为必填参数，防止覆盖历史 review_results.json。本批实际数据退出码 2 是预期的物理门禁拒绝，不是工具崩溃。

这是一份独立工具候选，勿直接替换带原清单哈希的历史包。`prepare/execute` 继承旧工具但本次未调用；候选目录不是完整 RTL 建造包，不以其默认路径启动物理构建。

## 交付内容

- `candidate.diff`、`original/`：原工具快照和主文件差异；新增策略模块单列。
- `test_pds_review.py`、`test_startup_console_gate.py`、`incoming/`：原 18 项回归和新增 66 项反例/集成测试及已有参考报告。
- `tests_normal.log`、`tests_optimized.log`：本次测试原始输出；测试产生的是合成夹具，不是 PDS 证据。
- `evidence/`：原 strict、候选 strict/适配结果及退出码记录、原件哈希。
- `real_log_excerpt/`：8 轮完整 console、回执、输入清单、实际 TCL 和时序报告，供离机复核；原日志不删 E 行。大数据库、位流、RTL/IP 仍在本机原运行目录，完整真实回放需这些原件。
- `verify_real_runs.py`：本机只读回放脚本，使用已记录的 D 盘路径；目标结果文件已存在时拒绝覆盖，复跑请在新解压目录执行。
- `verify_delivery.py`、`MANIFEST_SHA256.json`：解压后校验所有交付文件。

后续优先处理 PAP_GROUP 叶级证据认定。本批只记入待汇总进展，总说明和任务清单继续 v2.0.3，未升版。

待您转交：请二号协作者复核精确启动条件、回执/产物链及独立绑定判定，勿把该结果作为 G6 通过依据。

本次工作主要由 GPT-6 模型完成。

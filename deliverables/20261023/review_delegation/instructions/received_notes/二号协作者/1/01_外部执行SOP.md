# G8 八种子执行 SOP

执行前由设计方登记 C14/II=1 独立实验契约及候选SHA、确认本轮正式验收口径。工具研发和本地自检已完成，不需要等待一号A+B或M03素材；正式物理结论仍须外部实际执行。

使用已安装的 **PDS 2022.2-SP6.4 build146967**；不安装/下载其他版本。将本包解压到短英文目录，例如 `D:/g8_gate`。输入目录保持不动；每次执行使用全新目录。以下 `python` 指本机 Python3.10+。

## 1. 预检（不启动PDS）

```powershell
cd D:/g8_gate
python -B tools/g8_preflight.py --inputs prepared_inputs --out D:/g8_preflight_01
# 下列默认命令同样只预检，不运行PDS：
python -B tools/g8_execute.py --inputs prepared_inputs
```

应显示 PASS、八轮各147输入、latency14、II1。原始run_plan中的 PREPARED_NOT_EXECUTED 保持冻结；实际执行状态写入新目录的batch_receipt，不修改原计划/哈希。

## 2. 独立实际跑批

```powershell
python -B tools/g8_execute.py --inputs prepared_inputs --out D:/g8_run_01 --pds-shell D:/pango/PDS_2022.2-SP6.4/bin/pds_shell.exe --timeout-seconds 7200 --execute
```

顺序执行种子2/3/5/7/8/9/10/11，placement/route相同。每轮有console_full.log、process_started.json、process_receipt.json；根目录有batch_receipt.json。实际超时可按宿主能力选择，所有轮统一记录；更改工具超时参数不改变冻结RTL/Tcl。

正常非零退出、超时会继续后续种子；Ctrl+C发生于受控子进程等待时，终止本次子进程树，余下轮记NOT_STARTED。失败、中断、未启动不删除、不替换、不重跑覆盖。需要重跑时另建完整新目录。强制关闭执行器/断电可能留下RUNNING中间记录，这批不得认定完整。

Windows超时/中断通过当前PID的 `taskkill /T /F` 处理；不按全局程序名称杀其他PDS。回执保留终止返回结果。程序若被外部强杀、PDS派生进程脱离所记录进程树等情况仍须人工检查，不能靠该回执认证全部外部状态。

不要只拷sbit或挑选好种子；不要在同一目录修改FDC、源文件、IP或Tcl。工具记录的是未认证执行证据，哈希不能证明物理机器/板端实际状态。

## 3. 执行检查及只读门禁

```powershell
python -B tools/g8_check_execution.py --run D:/g8_run_01 --out D:/g8_execution_check_01
python -B tools/g8_gate.py --run D:/g8_run_01 --out D:/g8_gate_review_01
```

两个输出均必须是新目录，不能在原运行证据内。执行检查器记录完整不等于构建成功；门禁保持每轮8分母，不以缺失轮当不存在。

默认strict拒绝console任何E/Error/Fatal。若实际SP6.4确实出现已知的两条初始化DB诊断，提交原始完整日志后可显式选择：

```powershell
python -B tools/g8_gate.py --run D:/g8_run_01 --out D:/g8_gate_review_startup_01 --console-policy startup-db-v1-g8
```

该策略只允许固定前缀位置、各一次的两条原文，并仍要求后续所有G8阶段完整且顺序正确；不允许额外错误、重复、移位，也不豁免阶段日志错误。策略名称写进报告，不自动选择。

若软件实际日志格式与此已验证格式不同，保留失败和原文回传，先修适配并测试，不能手改日志使之通过。

## 一次性回传

归档整个 `g8_run_01`、两个检查输出、工具包版本/发行SHA、设计方C14登记/验收口径，附R01–R14索引更新。全成功、失败、中断、原生数据库/网表/时序/资源/约束/位流全部保留。所有时间带时区，工具版本由原生CSV/PRR及启动日志交叉核验。

本包只需要回传新的G8物理试验；不再要求重跑或重发已经接收的原G7八轮。

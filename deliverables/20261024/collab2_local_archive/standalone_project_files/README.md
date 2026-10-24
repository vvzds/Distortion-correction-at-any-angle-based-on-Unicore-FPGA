# G6 布局聚拢试验回传包（2026-10-22）

**用途：交给已有 PDS 2022.2-SP6.4 的电脑做物理试验。不是验收通过版，也没有新生成位流。**
生产基线继续 G4 `9e9e0fc`；与摄像头标定工作无关。若无错误不进行回复。

## 本次改动

只在原 FDC 末尾追加 `u_corr_top.u_core.u_map` 的 `PAP_GROUP=g6_map_locality`，聚拢整个 map 模块。
这是覆盖 sx/sy 两路的**粗粒度软分组试验**，不是已验证的精确树区域约束；可能改善，也可能因拥挤变差。
全部 RTL、IP、引脚、125MHz 约束和计算位宽不变；相对当前 G6 不增加延迟。G4 的 C11 → G6 的 C12、II=1 继续保持。
`run_g6.tcl` 已按原 SHA 重建；原包的 `impl.tcl/build.pds` 含旧电脑绝对路径，不作为本包入口。

## 在 SP6.4 电脑执行

需要 Python 3.10+ 标准库；不用安装任何 Python 包或新 PDS。把本包解压到纯英文目录，例如 `D:/g6_locality_pkg`。
以下在 PowerShell 执行；PDS 路径替换成那台电脑**现有 SP6.4** 的真实路径。

```powershell
cd D:/g6_locality_pkg
python tools/pds_review.py prepare --out D:/g6_locality_runs_20261022
python tools/pds_review.py execute --run D:/g6_locality_runs_20261022 --pds-shell 'D:/实际安装目录/PDS_2022.2-SP6.4-win64/bin/pds_shell.exe' --limit 1
```

先检查第一轮 `console_full.log` 无新增属性对象未找到、属性不支持或忽略警告。
检查 `binding_mapped.fdc/binding_groups.fdc`：`N78_*`、`N82_*` 两侧的叶级实例均有该 PAP_GROUP。
若导出只有模块属性或没有属性，本工具不会确认绑定；在 PCE/网表属性中确认并导出真实叶级约束，保存截图/日志后回传，勿盲目跑剩余 7 轮。
本地 SP6.1 仅核对官方语法，本包没有替 SP6.4 证明绑定成功。可在 PCE 属性里查看该组，**不要拿 CLMA 名字后缀当区域 XY 坐标**。

第一轮绑定正常，再执行同一命令去掉 `--limit 1`，它只运行尚无回执的剩余轮次：

```powershell
python tools/pds_review.py execute --run D:/g6_locality_runs_20261022 --pds-shell 'D:/实际安装目录/PDS_2022.2-SP6.4-win64/bin/pds_shell.exe'
python tools/pds_review.py collect --run D:/g6_locality_runs_20261022
```

默认种子 2/3/5/7/8/9/10/11，均同时设置 gplace/groute，逐轮串行，不修改原宿主目录。
已运行但失败的种子不自动重跑覆盖；若要复试，使用新的 `--out`，保留本轮全部结果。
collect 返回 0 仅表示该工具的物理试验门禁通过，**不表示 S1–S5 整模块通过**；非零时看 `review_results.json`。
PDS 属性忽略警告仍须人工核对全文；工具检查不能代替 PCE 对属性与实际布局效果的复核。

## 回传内容

整个 `D:/g6_locality_runs_20261022` 打包回传，含计划、8 轮控制台和退出码、源输入哈希、全部报告、网表、导出约束、rtr.db、sbit、汇总 JSON。
不要仅提交通过轮。附那台 SP6.4 的版本和绑定检查结论。本包不自动烧录、不晋升生产基线。
资源 .prr 也须保留；S3 仍需处理 cache DRM16 超 ≤12 及 APM 用途分配。

## 功能回归

`functional_replay` 是此前 G6 的完整自检工作集，四件 RTL 与本次宿主逐字节一致；历史结果单列存放，不伪装成本轮新跑。
若需要本轮独立回归，在有 ModelSim 的电脑创建纯英文可写临时父目录，然后运行：

```powershell
python functional_replay/tools/run_regression.py --vsim 'D:/实际目录/win64/vsim.exe' --scratch D:/g6_sim_scratch --only all
```

该工具覆盖 map、G4等价、行缓存、插值、读协议、T0–T9和全真 corr_top I0–I7。历史 reference suite/全套原始任务书需设计方按原版本复跑，本包不把缺失的独立 reference suite 判为已过。
新日志与 `functional_replay` 的输入哈希随物理回件一起返回。
注意已有功能 PASS **不等于性能全过**：若干非恒等参数仍超过 2 拍/像素，详见独立状态说明。

## 包内证据

- `evidence/candidate_input_comparison.json`：每件输入的新旧哈希及启动脚本重建。
- `evidence/received_default`：收到的原始默认轮报告，非本次新跑。
- `evidence/default_two_views.json`：对原始报告独立解析的两套数值和全部时钟域。
- `evidence/tool_selftest.log`：门禁单测结果；合成测试数据仅用于脚本验证，不是 PDS 产物。
- `docs/STATUS.md`：事实、未完成项、后续路线。
- `MANIFEST_SHA256.json`：全文件哈希；清单和压缩包的哈希另存包外 `SHA256_ANCHOR.txt`。

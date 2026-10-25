# A+B P5 缓存分组候选

先读[结果与回传说明](审查结果与回传说明.md)及[P5设计与验收口径](P5设计与验收口径.md)。功能证据通过与物理时序通过是不同结论，请以原始报告和结果JSON为准。

- `physical/host_seed2/analysis.tcl`：完整125MHz seed2宿主，139项原始源码/IP/FDC输入，没有位流步骤。
- `candidate/`、`tests/`、`baseline/`：冻结核心、分组cache、测试和R0完整对照证据。
- `results/`：五组逐拍、九种负例、三项完成回归与R0对照；另外两项受控中断、一项未运行。物理未完成，无最终时序结论。
- `GIT_MANIFEST.json`：逐文件SHA和省略的可再生成数据库清单。桌面ww/待转交另存包含中间产物的完整离线ZIP。

复现请在副本中使用新输出目录，避免覆盖既有证据。Icarus需要显式指定本机tool-root；PDS驱动固定原FDC/IP和seed2。core/map与接口/周期未改，核心调度与严格cpp≤2继续归二号；不是板级已验收版，不合并main。

# PDS 顶层解析恢复入口与证据

制作：二号协作者；接收：执行者/管理方；一号协作者可查阅。

原工程：`D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/full_source_1080p30.pds`。

## 当前结论

- 原工程已配置 `hdmi_ddr_ov5640_top`，并非工程文件漏写顶层。
- 115 个工程文件引用均存在；139 个冻结输入 SHA256 全部匹配。
- GUI 日志显示 20:04:47 启动层次解析，20:04:49 Compile 报 Flow-0245；层次更新尚未完成为候选原因，未据此断言唯一根因。
- 原生 Compile 已通过，耗时 174.01 秒，错误数 0；保留原有警告。
- 没有修改 RTL、IP、FDC、时钟、分辨率；没有重新生成位流、烧录或下发 UART。

## 本机下一步

本机已验证工程入口：`D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/top_recovery/full_source_top_recovered.pds`。在 PDS 中关闭原项目（避免把旧项目覆盖保存到新入口），然后打开此工程。顶层已固定，Compile 已完成；后续可从 Synthesize 开始。该副本保留原工程布局种子4、布线种子5、多角保持修复与20次迭代设置。

如需重复独立 Compile，双击 `D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/top_recovery/run_compile.cmd`，保持窗口打开。程序在独立目录中重新导入冻结源码，显式执行 `compile -top_module hdmi_ddr_ov5640_top`，只执行 Compile。

也可在当前工程的 PDS Console 输入 `source {D:/FPGA PDS/yx/DCSjingtaijiaozheng/01_project/compile_explicit_top.tcl}`；它对当前工程执行 Compile，会更新当前工程编译结果，因此优先使用独立目录入口。

日志与回执：`top_recovery/runs/<时间>/console.log`、`receipt.json`；只有 `state=PASS` 才是本轮 Compile 成功。

## 包内内容

`PDS_top_recovery.zip` 包含完整的原样 source、ipcore、FDC、原生 Compile 数据库、已完成 Compile 的 .pds、显式顶层 Tcl、运行器与本次日志，不含 PDS 安装包。解压后可打开 `full_source_top_recovered.pds`；重复编译在正常桌面双击 `run_compile.cmd`。PDS 默认安装路径为本机 SP6.1；安装位置不同时需修改 run_compile.py 的 tool 路径。不把 Compile 通过等同于综合、布局布线、时序或板测通过。

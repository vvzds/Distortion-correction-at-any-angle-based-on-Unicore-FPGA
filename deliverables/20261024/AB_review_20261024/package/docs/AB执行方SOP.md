# A+B新哈希执行与回传SOP

本包core/host保持已验收AB RTL，core SHA为`9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68`。本轮工作是冻结AB的独立评估，非用户暂停的G4接核板测，也不是AB与新map融合。SIM_MODE=0；PG2L100H/FBG676/-6；目标125MHz，视频配置1920×1080@30。

## 已可执行的综合

解压“执行方”交付包后，将其中 `handoff/AB_frozen_synthesis_inputs.zip` 再解压到全新目录，进入 `AB_inputs`。Python仅标准库。不要直接在带有compile/synthesize的证据树上重跑，v2会拒绝覆盖。每轮用全新输入副本并保留全部失败记录：

```powershell
python -B -X utf8 tools/run_synthesis_v2.py --pds D:/tools/PDS/bin/pds_shell.exe --timeout 1800 --run-label executor_sp64_01
```

两个任务串行执行；启动器记录PID、完整命令/UTC时间/时限/退出、工具二进制前后SHA、所有source/ipcore/Tcl/FDC/PDS输入前后SHA、console及compile/synthesize产物SHA。PDS路径由参数提供；采用私有subst盘符规避中文/空格，结束释放。超时仅清理本次PID的进程树并保存原日志。综合完成与时序通过分别报告。输出位于 `evidence/executor_sp64_01/synth_core` 和 `synth_host`；v2只复核运行前固定路径集合，将工具新增.pds列为产物。v1原始误报及独立复核保留在原证据包；v2只做过记录逻辑回归，未冒充本轮PDS执行入口。

本机本轮使用SP6.1 build138931，不能冒称SP6.4。执行方若使用SP6.4，应独立目录重跑，保留真实版本和所有诊断。最差路径/资源数值以该次SNR为准。

## 映射/布局布线前的缺口

1. AB宿主FDC原字节保留，当前没有uart_rx/uart_tx约束。需E02实际连线、电气和I/O时序审查，不能复制别的候选管脚或自动放置后发布位流。
2. 独立核当前使用`-disable_io_insertion -frequency 125`做内部综合估计，没有冻结专用PNR wrapper及外部输入输出delay/false path口径；先由执行/设计方确定可信FDC及测量边界。大量参数端口unconstrained警告是范围限制，不能写“所有路径收敛”。
3. build.tcl是继承的历史全流程入口，末尾包含gen_bit_stream；本批**不要用它冒充约束已冻结的可下载流程**。完成E02/E03后在新目录记录diff及新输入身份再执行。
4. 不降低频率、分辨率或门槛；不为过时序改map/cache、不引入G8、不同候选门禁不能混用。AB独立核与宿主分别报告setup/hold，不用综合代替PNR。

## 必须保存的结果

每轮保存compile/synthesize/dev_map/place_route全部原生数据库和报告（实际目录/文件名依工具版本记录），包括ADF/DMR、网表、PCF、SNR/PRR/RTR、原CSV与holdfix两口径、slow/fast setup/hold、资源设备/模块两表及差异原因、critical warning和未约束路径。若获准生成sbit，保留本体/SHA，不能仅凭生成成功判时序PASS。不清理失败/中断轮，不只报最佳seed。

统计容量24KiB为有效图像数据，物理DRM和标签/FIFO单列。请核查cache/tag→DRM地址和map宽乘法最差路径，不仅抄总WNS。最终报告关联输入、工具、命令、限制及下一动作，交一份完整包。

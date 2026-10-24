# V1.2 参考包更新与复测（2026-10-15）

> 本文下方保留2026-10-15历史记录。2026-10-18已收到设计方T_LIM修复原件，两份SHA256与补发说明一致，活动参考基线已替换；param_mgr新增S13c–h后pulses=16、err=0，gamma err=0。最新证据见`logs/refill_20261018/`及`../doc/G1_处理回复_20261018.md`。V12-01参考模块差距已闭合；下述pulses=10和待修复描述仅适用于旧基线。

来源：用户提供的 `collab2_undistort_core_task_pkg_v1.2(1).zip`。按截图指令继续，不修改冻结的 core 外部端口。

## 文件核对

压缩包共 9 个文件，`verification/reference_package` 与用户 V1.2 ZIP 逐项 SHA256 核对为9/9一致。再与 D:/FPGA PDS/sty/collab2_undistort_core_task_pkg_v1.1 逐文件 SHA256 核对：任务书、两份契约、gamma RTL/TB、两份 do 共 7 个文件相同；只有 01_ref/param_mgr.v 和 01_ref/param_mgr_tb.v 不同。原目录只替换上述两份，未改其他参考文件。

## 参考自检

验证方法：原始 do 的 vlog 均 0 error、0 warning，但本机 ModelSim 10.7 自动优化加载报 Error loading design。用显式 vopt +acc 后运行。为保存本机未打印的 display 判决，仅在 verification/reference_tb_runs 中的临时 TB 副本最终 Summary 段追加 fopen/fdisplay/fclose，不更改输入、判据、时序或原始 01_ref。

观测信号：param_mgr TB 的 err、upd_cnt、o_params_valid、参数输出及 UART 回读；gamma TB 的 err、像素、有效和标记输出。

预期与实测：param_mgr S0–S14 最终 ALL TESTS PASSED，err=0，updated pulses=10；gamma G0–G6 最终 ALL TESTS PASSED，err=0。结果文件和 `reference_console_full.log` 位于 verification/logs。ModelSim 退出另有 FileWatch(fileName) Tcl 提示，保留原始提示，不据此推定 RTL 失败或通过。

## 接口适配

当前 core TB 直接驱动参数，没有例化 param_mgr，无需修改其端口连接。后续顶层应接出 o_params_valid，用于启动门控；core 本身保留参数范围兜底检查。0x02 payload 25 字节，下标 24 的 bit0 控制 aff_en，系数区仍为 24 字节小端序。

## 新差距 V12-01（需设计方修订参考模块）

|编号|条款|问题|建议|
|---|---|---|---|
|V12-01|评审 G02：tx/ty ±4096|param_mgr.v 的 T_LIM=32'sh0100_0000 实际是 Q16.16 的 256，注释写 4096；合法的 ±4096 会被 o_params_valid 拒绝。现有 S13 仅检查焦距边界，未覆盖平移边界。|设计方将 T_LIM 改为 32'sh1000_0000，增加 ±4096 与越界 1 LSB 向量后重发；二号不擅改 01_ref。|

此差距不阻塞 core 的独立直接驱动测试；未经修订不宣称 UART 全参数范围端到端验收完成。

## 当前 core 状态

已修复新帧开始时行标签未失效的问题。两帧不同槽、不同 RGB565 图案合计 4,147,200 像素逐点正确，rel 两次；每帧恒等稳态 2 拍/像素。T0–T9 的完整仿真、生命周期与缓存轨迹统计见 `doc/verification.md` 及 `verification/logs/core_suite_*`。

PDS 2022.2-SP6.1 在 compile 启动时报 Flow-0189，未产生综合资源与 WNS。不得把本记录当作 PDS 综合/时序通过证据。

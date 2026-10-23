# R07：原 G7 与 FIFO16 功能回归

本机 ModelSim SE-64 10.7 独立执行通过，工具退出0、断言/完成标记和输入前后SHA均核对；不是只接受来件 PASS 字样。

原 G7 十组：map、与G6等价、与G4对齐等价、C13/II=1流输入、cache、bilinear、协议及SIM_MODE、reference、T0–T9、corr_top I0–I7，全部通过。流测试2,608次检查、1,299次恒等及5次在途复位；I0–I7有9帧golden、pub_cnt=9、err=0、link_viol=0，I6状态字00080012。协议预期故障注入被捕获。

T0–T9中部分历史非恒等golden用例每帧抽查129,600点，完整帧输出2,073,600像素；不把这些旧矩阵虚报成全部逐像素golden。R09另用冻结真实参数补四个全像素帧；两种覆盖范围均明确保存。

FIFO16独立副本：连续帧与复位恢复共5个完整1080P帧、10,368,000次逐像素/坐标核对；6阶段复位恢复通过，与原core共30,108,130拍外部可观察输出逐拍一致。credit峰值16、FIFO峰值16；队列抽象2,448状态/16,416合法转移通过，容量15负例被拒绝。读指针故意加2的外部等价负例成功触发检测。

FIFO16受影响协议/SIM_MODE、T0–T9、I0–I7另独立通过。该候选四模块哈希与candidate_fifo16一致；原版八种子物理执行仍使用FIFO32，未被替换。

恢复TB的约束是**core与DDR bridge共同复位、冲掉旧返回**；这些PASS不证明“只复位core而旧DDR响应继续返回”也安全。后者应在明确系统契约后单独补证，不能借本测试泛化。

原G7证据：`functional/g7_original/`（来自本机scratch原始evidence）；FIFO16冻结复跑证据：`execution/5/evidence/fifo16_20261023_194742_688998`，另有`contracts_20261023_192525_889111`、`negative_20261023_192037_251981`。逐执行命令、时间、退出码、输入/输出SHA见`local_runs`；机读接收结果见`functional_summary.json`。

首次FIFO16生命周期运行期间，未参与该测试的负例脚本做了两处本机路径适配，外层宽范围清单因此inputs_unchanged=false；原RTL/TB和实际runner没有变化。该原始标记、差异和说明保留在`local_runs/fifo16_initial_integrity_explanation.json`，不抹成true；另行完整冻结复跑作为正式接收依据。

功能PASS不代表时序、资源、真实吞吐或板端通过，相关结论分别见R02–R06、R09和R11。

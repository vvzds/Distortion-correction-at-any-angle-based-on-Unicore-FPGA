# 一号 A+B R1–R4 补正回执包

先阅读 `R1-R4_补正验收回执_给一号协作者_20261023.md`。四个补正项按原范围通过，独立候选未晋升生产；本机 ModelSim 四项实跑通过，来件 Icarus 十六项为记录核验。

- 原件：完整来件 ZIP、独立回传表及收件 SHA；保留其中候选、工具、十六项记录和历史失败。
- 核验：本机输入/日志核验、核心/测试差异、生成器复现、原启动器失败和修正后四项完整回执。
- tools：仅修正 Path 参数分隔符的 ModelSim 启动器，不含工具软件本体。
- 参考：上一批补正要求及本轮 R3/R4 范围说明。

解压本包后运行 `python -B verify_delivery.py`，检查全包文件清单。外层完整 ZIP 哈希见包外 SHA256SUMS.txt / delivery_receipt.json。文件清单不自列，清单自身由外层 ZIP 锚定。

## 复现本机 ModelSim 检查

需要已有 Python3 和有可用许可的 ModelSim10.7。解压 `原件/G4_AB_R1_R4补正回传包_20261023.zip` 到一个新工作目录；内层根目录为 `G4_AB_R1_R4_20261023`。保留原启动器副本，将本包 `tools/run_modelsim_validation.py` 复制到该工作副本的同名位置；这是唯一执行适配，DUT/TB/向量不变。不要修改留档原件或把原清单误用于已适配的启动器。

从内层根目录执行，工具路径按实际位置填写，输出目录必须不存在：

```powershell
python -B -X utf8 tools/run_modelsim_validation.py --tool-root D:/FPGA/MODELSIM/win64 --cases r3_boundary identity real_joint c6_host_arb --out my_runs/modelsim_verified
```

原始日志保留当时的绝对路径与 UTC 时间；未携带可重建的 ModelSim work 库/WLF，不影响源码和运行记录核验。`核验` 下管理审计脚本记录本机历史路径，供审计参考；可移植仿真入口为上述 tools 脚本配合原件候选。七个延迟点中其余五个仅核验来件 Icarus 证据，未标成本机 ModelSim 结果。

同一接收人的候选原件、补丁、回执和核验证据已合成这一份 ZIP。若无错误不进行回复，不要求重复纯收讫或重复相同测试。总说明及任务清单保持 v2.0.3。

本次工作主要由 GPT-6 模型完成。

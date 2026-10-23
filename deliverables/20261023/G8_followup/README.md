# G8回传复核统一包（给二号协作者）

先读reports/R01-R14_统一回执_给二号协作者_20261023.md及G8_管理方复核报告_20261023.md。当前包为独立C14实验回执，生产G4不变，总说明v2.0.4不升版。

original_received保留原ZIP/清单/截图；execution为本机实际执行副本；local_modelsims为新十组证据；execution/G8_real_regression/runs中含来件历史和本机新三帧，具体归属由functional_audit及local_runs argv/时戳区分。原有子清单为来件历史清单，当前完整文件集以顶层files_sha256.json为准。

physical_g8保留8轮全部输入与原生输出/进程回执，native_g8是仅在副本执行的原生ADF转换，两个native_*_audit和path_diagnostics保存结构及关键路径。所有生成的sbit仅作证据，不是签核可烧录版本。

gate_g8是隔离门禁候选。其CLI只用内置可信清单；正式本批−0.05ns口径还须assess_registered_g8.py，不能将G6 −0.10ns参考字段当本批门槛。自测生成目录留在管理方本机、未转交；保留生成器、夹具和完整输出日志以复现测试。普通首次aux_cases目录未建失败日志亦保留。

arithmetic_local包含原截断检验与完整96位补充、受控负例的实际测试副本/结果；负例不属于候选源码。M03依赖包不重复打包，按requirements-verified.txt使用隔离环境，不替换全局Python。

解压后运行python -B verify_delivery.py核验完整文件集。管理脚本保留本机绝对路径，移机复验需把W/工具路径定位至当前解压目录；不得修改已冻结输入或用任意新清单覆盖门禁。

R10_reference为一号已完成补正的限定回执，不是新增给一号任务或A+B整体签收。旧v2.0.4两份资料已确认转交；本包为新的唯一待转交件。

本次工作主要由 GPT-6 模型完成。

GitHub存档为parts_manifest.json+parts/，运行python -B reassemble.py逐片及整包校验后得到完整ZIP。桌面pkg只放完整ZIP，无需逐片转交。

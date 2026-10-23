# A+B 阶段审查合并转交包（给一号协作者）

先读《审查结论与处理意见_给一号协作者_20261023.md》。阶段证据已接收；ModelSim 完整核编译需补正；125MHz 时序未通过，不晋升生产，不启动 map 修改。

- 原件：收到的候选 ZIP、报告、截图，原字节保留。
- 核验：395 项包清单核查、源码/向量哈希、生成器复现、四项 ModelSim PASS、三项编译阻塞日志。
- 参考：已批准管理裁定、C6 稿与未更新的 v2.0.3 总说明。历史状态以该版本日期为准，本轮新状态以本审查意见为准。
- manifest.json / SHA256SUMS.txt：清单不自包含自身哈希；外层留档有最终 ZIP 哈希。

复现：在独立工作目录解压原件 ZIP，使脚本旁存在 extracted/G4_AB_candidate_20261022；复制核验中的 run_modelsim.py 到该工作目录，检查 TOOL 为本机 ModelSim 路径，然后用 Python 执行 `run_modelsim.py cache72 segment mode_switch c6_display c6_host_arb real_v7_resume_stress identity_v7_resume`。输出到 modelsim_final；脚本拒绝覆盖旧结果，复跑请使用新工作目录。来件 README 的 Icarus 命令仍为原作者复跑入口。audit.py/supplement.py 使用本机只读 G4 路径，迁移时先配置基线位置。不得把别人的日志当成本机新实跑。

本机早期启动器路径错误记录保留于管理工作区 modelsim、modelsim_v2、modelsim_v3；正式模型结果仅取 modelsim_final。modelsim_verified 为功能相同的前次检查，其正常 finish 退出策略曾返回 3，最终启动器统一为 0 并重新运行四项，不能混用结果回执。

若无错误不进行回复；完成实质补正后一次性合包回传。不要逐件转交本包内部文件。

本次工作主要由 GPT-6 模型完成。

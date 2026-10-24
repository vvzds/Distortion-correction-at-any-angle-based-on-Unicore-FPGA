# undistort_map 验证记录

## 2026-10-18 G1流水修订

验证方法：原 `run_undistort_map.do` 零改动，560点独立real模型仍PASS；新增 `run_undistort_map_equiv.do` 与已验收提交209ff75逐事务比较，覆盖96组参数、背靠背输入与空拍、共35,136个有效坐标，逐位一致。最新日志在 `logs/g1_20261018/`。

观测信号：两版 `o_init_done` 必须相同；新 `o_valid` 必须严格等于旧valid延迟2拍；按有效事务排队核对源坐标，每帧结束核对已发/旧输出/新输出数量相同。

预期与实测：real测试560点err=0，等价测试35,136点err=0、extra_latency=2；未改变任何映射截断位置及对外端口。本机PDS仍Flow-0189，不能据此声称G1时序闭合。

## V1.2已验收基线

验证方法：ModelSim 10.7在ASCII路径运行`vsim -c -do run_undistort_map.do`。TB独立使用real数值计算屏幕域仿射、径向/切向畸变和坐标钳位，再与定点RTL的Q16.16源坐标比较。原有176点涵盖恒等精确直通、T3/T4参数、正负及半像素平移、fx=128与边界系数组合；2026-10-15再加入384点：最小焦距、仿射四系数±2、平移±4096的64种符号组合，各查3坐标与k2=±0.5。扩宽r4寄存器48→64位前失败64点，修复后560点全过。编译和优化均为0 error、0 warning；`map_result.txt`记录`=== ALL TESTS PASSED (err=0) === samples=560`，最新原始日志为`map_range_after_transcript.log`。

观测信号：`i_frame_init`、`o_init_done`、参数输入、`i_valid/i_u/i_v`、`o_valid/o_sx_q16/o_sy_q16`，以及TB `err/checks`。

预期现象：帧首两次迭代倒数计算后`o_init_done=1`；帧内按锁存参数产生映射坐标。恒等坐标逐位无损；其余点与独立real结果的X/Y坐标误差均≤0.02像素，越界钳位到图像边缘。此模块测试不等于完整T0-T9通过，也不能单独证明PDS资源/时序。r4使用signed64/Q24是本次功能修复，core外接口不变；仍不宣称穷尽全部合法参数组合。

工具提示：本机ModelSim退出时另打印`FileWatch(fileName)` Tcl提示；原始transcript和TB结果文件均保留。

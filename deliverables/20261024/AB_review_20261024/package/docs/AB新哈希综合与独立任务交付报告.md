# A+B新哈希综合与独立任务交付报告

2026-10-24整理交付，综合实际执行于2026-10-23。一号协作者。本报告追加新实跑事实，不替换管理方v2.0.4、不宣告生产晋升。用户本轮安排：优先A+B独立任务，G4接核/板测暂停，等待新的优化核心。

## 本轮结论

冻结A+B新core哈希 `9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68` 的独立核和真实宿主均完成本机PDS综合，但125MHz时序均未通过。没有修改RTL、生产G4或原FDC；没有加入新map/G8，没有执行dev_map/布局布线、生成位流或烧板。

| 本轮实际任务 | 工具 | LUT | FF | APM | DRM（36K等效） | 125MHz综合WNS | 结论 |
|---|---|---:|---:|---:|---:|---:|---|
| 独立A+B核 | PDS2022.2-SP6.1 build138931 | 21461 | 11548 | 105 | 9.0 | −0.796ns | 综合完成，时序FAIL |
| 真实A+B宿主 | 同上 | 28830 | 23310 | 105 | 22.5 | −1.226ns | 综合完成，时序FAIL |

器件PG2L100H/FBG676/−6；SIM_MODE=0；配置1920×1080@30。独立核121.844秒，宿主334.063秒，两个PDS进程均退出0，均有Synthesize done。原生报告记录本次2026-10-23生成时间。数值虽与旧报告相同，本次有新哈希输入/命令/PID/起止/日志及原生产物，未套用修正前结果。SP6.4复验仍未执行。

原生报告：`core/synthesize/undistort_core.snr`、`host/synthesize/hdmi_ddr_ov5640_top.snr`。完整命令、运行前后哈希及产物索引：`evidence/synth_core/process_receipt.json`与`synth_host/process_receipt.json`。

## 记录器误报与复核

v1记录器把PDS新生成的`ab_r1r4_core.pds`/`ab_r1r4_host.pds`误算成输入集合变化，因此两份原始receipt为FAILED，启动器返回1；这不等于PDS综合失败。原始receipt、console、v1脚本全部保留，未改成PASS。

`fixed_input_audit.json`固定运行前路径集合核验：core6项、host141项原输入均未变，各19项compile/synthesize产物、console及工具SHA均匹配。仅新增上述两个工具项目文件。独立复核PASS，综合完成；时序仍FAIL。

新增v2启动器按原路径集合复核，把新增项目文件单列；拒绝覆盖已有compile/synthesize目录。`evidence/runner_v2_check.json`记录6项记录逻辑/CLI检查PASS（包含修改、删除原输入的检测）。本轮PDS实际由v1执行，v2未重新跑PDS，不能混记。

## 关键路径及资源口径

独立核最差路径：`u_map/N46_m4/CLK → u_map/kr2_4[63]/D`；宿主：`u_correction/u_core/u_map/N46_m4/CLK → …/kr2_4[63]/D`，位于125MHz的`ddrphy_sysclk`域。两者均为原map宽乘法后的收敛路径；本轮未扩大map修改范围。

独立核原生单元为8个DRM36K＋2个DRM18K＝9.0等效；宿主16个DRM36K＋13个DRM18K＝22.5等效。map占87 APM、bilinear占18，总105；cache模块占8 DRM，独立核cache统计16677 LUT/8074 FF，宿主cache16670 LUT/8074 FF。分层优化会影响LUT/FF，不能直接按模块粗加替代设备总表。24KiB为缓存有效图像容量，不是“24KiB就等于全部物理RAM”；标签/LRU/FIFO及分布式存储另占资源。本轮没有dev_map资源表，不伪造综合与物理两表一致性。

## 警告及物理评估限制

完整警告原文和行号见`evidence/warning_index.json`、各`warning_lines.txt`及原console。计数按console出现次数，core1条、host54条C级诊断，不套用其他候选的38条。

- 独立核C级SDC-2025提示clk需要显式时钟约束。当前仅`-frequency 125`内部综合估计，外部参数等路径也有未约束提示；不能据此宣布全路径约束/收敛。PNR须冻结专用wrapper与FDC、I/O测量边界。
- 宿主18条未驱动诊断对应旧`cmos2_d_16bit[15:0]`、href/pclk调试网；检索当前top仅有带MARK_DEBUG的声明，无实际数据通路使用。保留原样并回传，不擅自删冻结网。另36条为原FDC share-pin提示，应按实际板卡/配置审阅。
- 宿主原FDC缺UART RX/TX引脚、电气和I/O约束；不猜引脚，不用自动分配结果发布下载位流。
- rd/wr_fram_buf IP元数据为FBG484而宿主为FBG676，日志有Flow-4058；需执行方核对IP适用性及是否需要重新生成，不能把综合完成当成此项闭环。
- 缓存存在last_use多写RAM不支持、反馈mux等综合提示；完整原件保留供资源/时序复核，不按警告条数直接认定功能失败或全部豁免。

`multiseed_summary.csv`中的PNR单种子栏全部NA，0%不是“已跑多个种子全部失败”；实际未做PNR。综合WNS、模型fps和板端新帧发布率三个证据层次分别保留。原生hold/setup物理结论尚缺，不生成可下载位流。

## 其他独立交付

T02 V1.1合并稿、原文/裁定/已收到ModelSim日志、diff及算术核对在`T02/`。已将R01恢复总历时3728与接受拍3724的口径及前提并入正文；没有改RTL/TB，也未重跑已闭环W0–W8。该稿由一号按已生效裁定整理，待设计方审阅归档，非设计方新签发版本。

新核心接入前检查、最终网表W9/W10与FIFO记录准备、待协作者统一材料清单均已完成。新优化核心未收到，兼容性实际核验/融合未开始。M01软件已有普通/−O独立复验；P10及真实FIFO/画质素材受本轮暂停安排影响，保持未测。全部任务状态见`任务台账与续接.md`。

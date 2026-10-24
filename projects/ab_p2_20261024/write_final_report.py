"""Build a factual review from completed native evidence (not exit status alone)."""
from pathlib import Path
import json
R=Path(__file__).resolve().parent
def load(p):return json.loads((R/p).read_text(encoding='utf-8'))
run=load('results/physical_seed2/process_receipt.json')
assert run['state']=='FINISHED' and run['exit_code']==0 and not run['changed_input_files']
assert not run['bitstreams_present']
cmp=load('results/physical_comparison.json')
p1=load('prior_p1/physical_comparison.json')['candidate']
versions={'R0':cmp['baseline'],'P1':p1,'P2':cmp['candidate']}
warn=load('results/warning_comparison.json')
assert load('results/regression_comparison.json')['passed']
assert all(x['pass'] for x in load('results/equivalence_p2/summary.json')['results'])
assert all(x['detected'] for x in load('results/negative_checks_p2/summary.json'))
assert all(x['passed'] for x in load('results/regression_p2/summary.json')['results'])
assert all(v['pnr_two_tables_match'] for v in versions.values())
def corner(v,kind,corner):return next(t for t in v['timing_summary'] if t['kind']==kind and t['corner']==corner)
def row(v):return next(x for x in corner(v,'Setup','Slow')['rows'] if x['launch']==x['capture']=='ddrphy_sysclk')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
timing=[]
for kind,c in [('Setup','Slow'),('Setup','Fast'),('Hold','Slow'),('Hold','Fast')]:
    timing.append([f'{kind} {c} WNS/ns']+[f'{corner(v,kind,c)["worst_slack_ns"]:+.3f}' for v in versions.values()])
timing.extend([['Slow DDR TNS/ns']+[f'{row(v)["total_slack_ns"]:.3f}' for v in versions.values()],['Slow DDR失败端点']+[row(v)['failing_endpoints'] for v in versions.values()]])
resources=[]
for inst,label in [('hdmi_ddr_ov5640_top','整机'),('+ u_core','核心'),('+ u_cache','缓存')]:
    for metric in ['LUT','FF','Distributed_RAM','APM','DRM']:
        resources.append([label+' '+metric]+[f'{v["resources"]["pnr"][inst][metric]:g}' for v in versions.values()])
paths=[]
for n,p in enumerate(cmp['candidate']['worst_reported_paths'][:5],1):
    paths.append(f'{n}. `{p["start"]}` → `{p["end"]}`：slack {p["slack_ns"]:+.3f}ns；逻辑 {p.get("logic_ns","未列")}ns，布线 {p.get("route_ns","未列")}ns。')
category=[]
for label,ps in cmp['candidate']['reported_path_categories'].items():
    if ps:
        p=ps[0];category.append([label,p['type'],f'{p["slack_ns"]:+.3f}',f'`{p["start"]}` → `{p["end"]}`'])
    else:category.append([label,'未列出','原生抽样路径未列出','不能据此认为该类所有路径都已通过'])
passed=cmp['all_reported_setup_hold_nonnegative']
status='四角报告setup/hold非负；仍不等于板端验收通过' if passed else '125MHz物理时序未通过，不得晋升生产或据此烧板'
delta=row(cmp['candidate'])['slack_ns']-row(p1)['slack_ns']
warning_rows=[[x['category'],x['R0'],x['P2']] for x in warn['counts'] if not x['category'].startswith('UNCODED')]
doc=f'''# A+B P2缓存优化：结果与回传说明

本轮缓存候选已完成实现、功能对照、完整帧回归和固定seed2布局布线。**功能/周期门禁通过；{status}。** P2相对P1的Slow DDR WNS变化为{delta:+.3f}ns（正值表示改善），实际值见下表。不得用工具退出0或模型fps代替时序/实板结论。

**本轮裁定：P2时序和LUT成本均劣于P1，不采纳为下一版基线；保留为可追溯的未采纳候选。P1仍只是较好参考，也未满足125MHz。** 完整项目上传是实验留档，不是生产晋升。

## 1. 范围与输入

用户已授权直接开展下一轮缓存优化，并自动上传今后的完整工程。本轮只改变`undistort_cache_ab.v`；1920×1080@30、接口、输出周期、DDR契约、24KiB缓存、FIFO512、lookahead256保持，未改core/map/bilinear、FDC/IP/UART，未扫seed、降频或生成位流。静态映射核心仍归二号。

P2在已有Q_SELECT阶段按所属16槽组并行生成全部初始命中mask，保留最高组及组内最高项优先级；Q_ALLOC补入分配槽，删除Q_CHECK到mask的串行译码。原淘汰保护、touch优先级、沿前退休比较、时间戳不复位语义保持。详见`P2设计与验证口径.md`和`diffs/`。

- R0缓存SHA：`4fc449dc3bf1e34711c774057c4d92559ebd545e5f88facac27cac5da33a6a60`。
- P1缓存SHA：`8cf12b084c4915887e06318355cd9252d70756b8eae155a8b523f40069674fe5`。
- P2缓存SHA：`ecc95ddacbc2138b390f5fda48e9494a2ccbd5db17790a2768a5cf5ca76d58a4`。
- 冻结core SHA：`9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68`。
- 物理宿主139项输入只允许缓存差异，本轮运行前后全部未变；仿真候选81项输入及与原版差异见身份表。

## 2. 已完成的功能验证

- 5组缓存原版/P2双实例逐拍比较通过，包含状态、端口、时间戳、标签及FIFO。定向72组、1027沿、54次完成、77次分配、2次分配等待；全命中仍7沿。新增12个组/两个奇偶、同组与跨组重复标签、最高优先级及mask集合不变量检查。
- 5项故障注入均被断言检出：遗漏第四命中、忽略组优先级、遗漏分配槽、初始mask残留、错误touch优先级。负例FATAL是预期检出，不是候选失败。
- identity、real_joint、legacy_sim、integration、c6_real_subsystem、c6_host_arb六项全部通过。参数、输入差异、完整规范化日志与R0一致；仅移除finish行的绝对路径，保留行号、时间和数值。
- 部分定向元数据通过对两个实例对称层级赋值建立；使用Icarus，未声称ModelSim、形式证明或板测。

identity为4,147,487周期/2,073,600像素。real_joint为4,161,845周期、26,695事务、106,780返回拍，实际首拍65–66、间隔2、grant32；cpp=2.007063，假设125MHz的模型fps=30.034756。**原有cpp≤2门槛仍未满足**，没有因本轮等价优化而改变。c6真实子系统和宿主仲裁为4,147,513周期、1,036,800字；commit到publish为17周期。以上是各自TB口径，不能混作物理运行或实测发布率。

## 3. 原生物理结果

PDS 2022.2-SP6.1 build138931，PG2L100H/FBG676/-6，125MHz，布局和布线seed均2。运行UTC：`{run['started_utc']}` 至 `{run['finished_utc']}`。退出0、输入不变、无sbit；完整原生snr/dmr/prr/rtr、CSV、hold-fix摘要和console均保留。

{table(['指标','R0','P1','P2'],timing)}

最终rtr与multiseed_summary.csv一致：CSV的State=OK仅表示流程完成，Convergence=Fail才是本轮收敛状态。中间hold-fix摘要曾给出WNS=-2.646ns/TNS=-3944.402ns/5366失败端点，最终report_timing更新为上表数值；不采用中间摘要替代最终结果。相对P1最终WNS退步0.883ns、TNS恶化2353.211ns、失败端点增加1647；相对R0 WNS也退步0.160ns。

PNR全局资源与层级根节点两张表逐项一致：

{table(['PNR资源','R0','P1','P2'],resources)}

P2最差的已报告路径：

{chr(10).join(paths)}

按类别查看已报告路径（原生报告只列部分路径，未列出不代表不存在）：

{table(['类别','路径类型/工艺角','最差已列slack/ns','路径或说明'],category)}

最差路径已转为core的prep_ptr[3]经touch相关组合通路到cache的last_use[99]写使能：总数据延迟10.158ns中布线8.287ns，约81.6%。这说明本次并行化没有解决整体控制扇出/布线负担；仅凭qs→mask不在抽样最差列表中，不能认定这类路径全部合格。相对P1整机LUT增加459（缓存增加465）、FF减少1，缓存仍8 DRM。后续若继续，应以P1为比较参考，优先分析缓存内touch/时间戳写使能的局部译码及扇出；不能为此单方面修改二号维护的core/map或增加可见延迟。本轮没有继续启动P3。

单seed结果用于比较本轮候选，不代表跨seed稳定性，也不代替完整板级约束审核与实测。

## 4. 告警和约束限制

{table(['console类别','R0次数','P2次数'],warning_rows)}

E级行：R0={warn['evidence']['R0']['error_count']}，P2={warn['evidence']['P2']['error_count']}；C级行：R0={warn['evidence']['R0']['critical_count']}，P2={warn['evidence']['P2']['critical_count']}。不能只扫描W/E而漏掉C。未复位last_use反馈提示：R0={warn['evidence']['R0']['last_use_feedback_count']}，P2={warn['evidence']['P2']['last_use_feedback_count']}；静态写入后的按位反馈提示需结合实现解释，不为消除提示而增添复位。所有告警原文及关键字筛查见`results/warning_comparison.json`，统计不等同于豁免。

原诊断宿主UART RX/TX未固定板级引脚，PDS自动选点不能用作接线建议；原基线N6相关电气问题不因自动换点而视为关闭。继承的legacy camera16bit未驱动置0等C级诊断继续保留。最终工程仍需可信板级约束；本轮不改FDC。未运行ModelSim、SDF、位流或实板检查。

本轮prr自动分配uart_rx=J16、uart_tx=L14，仅记录工具结果，**不是板卡UART引脚建议**。新增告警关键字筛查为0；Sdm-2010多写提示从1到0、Sdm-2014从2742到6774，与P1引入静态timestamp写入一致。C级还包括共享引脚、悬空旧端口、SCCB时钟SRB布线以及non_unate时钟弧，均未被“E=0”结论豁免。

## 5. 交付与后续

源码、测试、向量、139项物理宿主输入和全部验证证据位于本目录。复现入口见`复现与证据说明.md`；`physical/host_seed2/analysis.tcl`是实际compile/synthesize/dev_map/pnr/report_timing入口。生成的impl.tcl可能含运行时SUBST路径，仅作为过程产物，不作为跨机器入口。

本地完整ZIP放在ww/待转交；上传完整可复现候选至仓库独立分支`contributor-01/ab-p2-20261024`、目录`projects/ab_p2_20261024`，并创建草稿PR。Git省略可重新生成的PDS数据库/中间网表和仿真可执行文件，保留全部声明输入和原生证据；逐文件清单为GIT_MANIFEST.json。实际提交、PR链接及逐文件校验记录在ww的GitHub上传回执。没有自动合并main。

**给二号协作者**：完整候选工程、cache差异、输入身份及功能/时序证据，供后续整机方案比较；不代表已批准替换核心或生产基线。**给管理方/设计方（如需归档）**：本报告及原生结果；用户已授权直接进行本轮，归档不作为本轮实施前置。**暂不交执行方烧录**：本包无位流，也未完成板级验收。
'''
(R/'审查结果与回传说明.md').write_text(doc,encoding='utf-8')
(R/'README_当前进度.md').write_text(f'''# A+B P2缓存候选：本轮验证已完成

5组逐拍对照、5种故障注入、6项完整帧/整机回归与R0全量规范化日志对照均已通过。固定seed2的PDS已完成；**{status}**。

先读[审查结果与回传说明](审查结果与回传说明.md)，复现见[说明](复现与证据说明.md)。P1保留；本轮只改缓存，未改core/map、接口或输出周期。

完整工程按用户授权自动上传仓库独立分支和草稿PR；本地ZIP保留在ww/待转交。上传链接以ww/AB_P2_GitHub上传回执_20261024.json为准。
''',encoding='utf-8')
print(json.dumps({'status':status,'p2_vs_p1_wns_delta_ns':round(delta,3),'report':str(R/'审查结果与回传说明.md')},ensure_ascii=False,indent=2))

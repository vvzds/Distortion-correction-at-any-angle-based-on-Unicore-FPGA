from pathlib import Path
import json,hashlib,re,csv,datetime
R=Path(__file__).resolve().parent
def load(p):return json.loads((R/p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(h,rows):return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join(['---']*len(h))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])
run=load('results/physical_seed2/process_receipt.json')
assert run['state']=='FINISHED' and run['exit_code']==0 and not run['changed_input_files'] and not run['bitstreams_present']
assert sha(R/'results/physical_seed2/console.log')==run['console_sha256']
comp=load('results/physical_comparison.json')
reg=load('results/regression_comparison.json');assert reg['passed']
assert all(x['pass'] for x in load('results/equivalence_p3/summary.json')['results'])
assert all(x['detected'] for x in load('results/negative_checks_p3/summary.json'))
p1=load('prior_p1/physical_comparison.json')['candidate']
versions={'R0':comp['baseline'],'P1':p1,'P3':comp['candidate']}
for v in versions.values():assert v['pnr_two_tables_match']
for row in load('candidate_identity.json')['files']:assert sha(R/'candidate'/row['file'])==row['sha256']
for row in load('physical/input_identity.json')['inputs']:assert sha(R/'physical/host_seed2'/row['file'])==row['sha256']
def corner(v,k,c):return next(x for x in v['timing_summary'] if x['kind']==k and x['corner']==c)
def ddr(v):return next(x for x in corner(v,'Setup','Slow')['rows'] if x['launch']==x['capture']=='ddrphy_sysclk')
timing=[[k+' '+c+' WNS/ns']+[f'{corner(v,k,c)["worst_slack_ns"]:+.3f}' for v in versions.values()] for k,c in [('Setup','Slow'),('Setup','Fast'),('Hold','Slow'),('Hold','Fast')]]
timing.extend([['Slow DDR TNS/ns']+[ddr(v)['total_slack_ns'] for v in versions.values()],['Slow DDR失败端点']+[ddr(v)['failing_endpoints'] for v in versions.values()]])
resources=[]
for scope in ['hdmi_ddr_ov5640_top','+ u_cache']:
 for metric in ['LUT','FF','DRM','APM']:
  resources.append([scope+' '+metric]+[f'{v["resources"]["pnr"][scope][metric]:g}' for v in versions.values()])
cpp_line=next(s for x in reg['results'] if x['case']=='real_joint' for s in x['candidate_summary'] if 'CORE PASS' in s)
cpp=float(re.search(r'cpp=([\d.]+)',cpp_line)[1])
timing_pass=comp['all_reported_setup_hold_nonnegative']
wns=ddr(comp['candidate'])['slack_ns'];delta=round(wns-ddr(p1)['slack_ns'],3)
cache_budget=comp['candidate']['resources']['pnr']['+ u_cache']['DRM']<=12
console=(R/'results/physical_seed2/console.log').read_text(errors='replace')
map_diag='COMPLETED' if 'P3_MAP_DIAG_COMPLETED' in console else 'FAILED_OR_NOT_RUN'
base_restored='P3_UNRESTRICTED_REPORT_RESTORED' in console
assert base_restored,'Unrestricted report restoration was not recorded'
rows=list(csv.reader((R/'physical/host_seed2/multiseed_summary.csv').read_text().splitlines()))
head=next(x for x in rows if x and x[0]=='Seed');vals=next(x for x in rows if x and x[0]=='single');csvrow=dict(zip(head,vals))
for t in comp['candidate']['timing_summary']:assert float(csvrow[f'{t["kind"]}({t["corner"]})'])==t['worst_slack_ns']
paths=[]
seen=set()
for p in comp['candidate']['worst_reported_paths']:
 key=(p['start'],p['end'],p['type'])
 if key not in seen:
  seen.add(key);paths.append([f'`{p["start"]}`',f'`{p["end"]}`',p['type'],p['slack_ns'],p.get('logic_ns'),p.get('route_ns')])
 if len(paths)==6:break
status='物理四角报告通过' if timing_pass else '125MHz物理时序未通过'
text=f'''# A+B P3结果与后续

本轮功能/周期检查通过；整机**{status}**。P3相对P1最终DDR WNS变化{delta:+.3f}ns，正值表示改善。用户已确认本轮一号只负责缓存125MHz优化；核心调度与吞吐由二号负责。严格吞吐cpp={cpp}，{'满足' if cpp<=2 else '仍不满足'}cpp≤2，此项记录供二号处理，不作为一号继续修改核心的授权。缓存是否收敛另见results/focused_timing.json及实际定向报告；整机未通过不能直接推出每个缓存路径未通过，缓存通过也不等于整机通过。没有生产合并或烧录。

## 变更及身份

从P1出发，只删除last_use更新循环外层冗余的alloc/DONE/touch全局条件。逐槽条件、写入优先级、沿前退休读取、时间戳不复位、mask维护、查找完成周期保持。core/map/bilinear、DDR、24KiB缓存、FIFO512、lookahead256和FDC/IP未改。P2并行译码未沿用。

cache SHA：`614797ccd5a2f122caed1050fc013e28e3852f14923b3a037fa7c5d453a65330`。81项仿真输入仅cache不同；139项物理输入有cache及analysis.tcl两项差异，后者仅增加报告路径和可选map/cache-from/cache-to定向报告，不改变综合、PNR、125MHz或seed2。输入运行前后不变。

## 功能验证

五组原版/P3逐拍对照通过，定向58组/862沿、40次完成、77次分配、2次等待、全命中仍7沿。五种故障注入全部被检出。identity、real_joint、legacy_sim、integration、c6_real_subsystem、c6_host_arb六项通过，参数、规范化完整日志和周期与R0一致。部分定向元数据对称层级置入，保留未知态；这是Icarus仿真，不是形式证明或ModelSim实跑。

真实压力场景原始摘要：

```text
{cpp_line}
```

模型fps按125MHz假设计算，不代表物理可运行或板端新帧发布率。保持逐拍等价也意味着没有消除原有cpp超限。

## 固定seed2物理结果

PDS 2022.2-SP6.1 build138931，PG2L100H/FBG676/-6。UTC运行起止：{run['started_utc']}至{run['finished_utc']}。原生rtr/CSV四角数值一致，CSV状态{csvrow['State']}、收敛{csvrow['Convergence']}；流程退出0不等于时序合格。

{table(['指标','R0','P1','P3'],timing)}

{table(['PNR资源','R0','P1','P3'],resources)}

P3整机根节点和器件资源表完全一致；缓存DRM≤12预算{'通过' if cache_budget else '未通过'}。不因时序变化豁免原有约束和告警。

最差已报告路径：

{table(['起点','终点','类型','slack/ns','逻辑/ns','布线/ns'],paths)}

辅助map报告执行状态：{map_diag}；不加起点过滤的整机报告已恢复。辅助结果必须查看实际匹配对象/路径才可解释，无路径不等于map通过。默认完整报告和CSV才是整机判据；原生报告位于physical/host_seed2/report_timing，辅助报告位于report_timing_map_diagnostic（如生成）。

## 限制及交付

本轮无sbit、无上板；原诊断UART未固定有效板级LOC，自动分配不是接线建议。继承的SCCB/共享引脚/悬空旧端口/时序覆盖等告警保留；compare_warnings统计及原文见results。辅助报告可能重复产生时序提示，应区分原完整流程与辅助诊断。

P1/P2原包不变。完整工程按用户授权上传独立分支contributor-01/ab-p3-20261024，仓库目录projects/ab_p3_20261024；实际提交与PR链接以ww上传回执为准。离线ZIP在ww/待转交。给二号工程与验证证据供协作，管理方可归档；当前不发烧录任务。缺失资料先查仓库，核对版本、契约和SHA后使用。
'''
(R/'审查结果与回传说明.md').write_text(text,encoding='utf-8')
(R/'README_当前进度.md').write_text(f'# P3本轮结果\n\n功能/周期通过；{status}，WNS {wns:+.3f}ns；cpp={cpp}。详见审查结果与回传说明.md。整体仍非板端验收通过版本。\n',encoding='utf-8')
out={'verification_passed':True,'timing_passed':timing_pass,'cpp_passed':cpp<=2,'cpp':cpp,'cache_budget_passed':cache_budget,'wns_ns':wns,'delta_vs_p1_ns':delta,'unrestricted_report_restored':base_restored,'map_diagnostic':map_diag,'input_files_verified':{'candidate':81,'physical':139},'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(R/'results/final_evidence_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))

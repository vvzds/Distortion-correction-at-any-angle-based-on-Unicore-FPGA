"""Audit closed processes and complete logs before writing any P5 conclusion."""
from pathlib import Path
import json,hashlib,re,datetime,subprocess,sys
R=Path(__file__).resolve().parent;W=R.parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
eq=load(R/'results/equivalence_p5/summary.json');neg=load(R/'results/negative_checks_p5/summary.json')
reg=load(R/'results/regression_comparison.json')
run=load(R/'results/physical_seed2/process_receipt.json')
assert run['state']!='RUNNING' and run['state']!='STARTING'
assert not run['changed_input_files'] and not run['bitstreams_present']
assert sha(R/'results/physical_seed2/console.log')==run['console_sha256']
assert not run.get('owned_processes_remaining',[])
for row in load(R/'candidate_identity.json')['files']:
    assert sha(R/'candidate'/row['file'])==row['sha256'],row['file']
for row in load(R/'physical/input_identity.json')['inputs']:
    assert sha(R/'physical/host_seed2'/row['file'])==row['sha256'],row['file']
assert sha(R/'candidate/source/rtl/undistort_core.v')=='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
functional=all(x['pass'] for x in eq['results']) and len(eq['results'])==5 and len(neg)==9 and all(x['detected'] for x in neg) and reg['passed'] and len(reg['results'])==6
assert functional,'Preserve failure evidence; do not issue passing functional receipt'
completed=run['state']=='FINISHED' and run['exit_code']==0 and (R/'physical/host_seed2/report_timing/hdmi_ddr_ov5640_top.rtr').exists()
timing=None;wns=None;corners=[]
focused=None;cache_verdict='NOT_ESTABLISHED'
if completed:
    subprocess.run([sys.executable,'-B',str(R/'inspect_physical.py')],check=True)
    phys=load(R/'results/physical_comparison.json');corners=phys['candidate']['timing_summary']
    assert phys['candidate']['pnr_two_tables_match']
    timing=phys['all_reported_setup_hold_nonnegative'];wns=min(x['worst_slack_ns'] for x in corners if x['kind']=='Setup')
    focused=load(R/'results/focused_timing.json');assert focused['original_evidence_unchanged']
    cache_verdict=focused['cache_closure']
line=next(s for x in reg['results'] if x['case']=='real_joint' for s in x['candidate_summary'] if 'CORE PASS' in s)
cpp=float(re.search(r'cpp=([\d.]+)',line)[1])
console=(R/'results/physical_seed2/console.log').read_text(errors='replace')
snr=R/'physical/host_seed2/synthesize/hdmi_ddr_ov5640_top.snr'
resources=[s for s in snr.read_text(errors='replace').splitlines() if '+ u_cache ' in s] if snr.exists() else []
status='整机受约束路径物理四角通过（仍需板级证据）' if timing else ('整机物理时序未通过' if completed else '物理未完成，未取得125MHz收敛证据')
result=dict(verification_passed=functional,physical_completed=completed,timing_established=completed,timing_passed=timing is True,wns_ns=wns,
    physical_state=run['state'],cpp=cpp,cpp_passed=cpp<=2,core_schedule_owner='二号协作者',
    cache_focused_timing_established=cache_verdict in ('FAIL','PASS_UNDER_EXISTING_CONSTRAINTS'),cache_focused_verdict=cache_verdict,
    cache_timing_passed=cache_verdict=='PASS_UNDER_EXISTING_CONSTRAINTS',corners=corners,cache_synthesis_rows=resources,
    timestamp_feedback_warning_count=sum('Feedback mux' in s and ('last_use' in s or "signal 'age[" in s) for s in console.splitlines()),
    error_lines=[s for s in console.splitlines() if s.startswith('E:')],
    source_cache_sha256=sha(R/'candidate/source/rtl/undistort_cache_ab.v'),candidate_inputs_verified=81,physical_inputs_verified=139,
    new_bitstreams=[],board_validated=False,next_method_started=False,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
dump(R/'results/final_evidence_verification.json',result)
text=f'''# P5缓存分组结果与交付

功能与周期验证通过；**{status}**。固定125MHz、seed2、core/map、FDC/IP和接口，没有生成位流或上板。本轮只负责缓存优化；严格cpp≤2的核心调度继续由二号负责。

## 实现与身份

192项元数据拆成12组×2奇偶×8槽，保留原平坦只读视图；row/seg/age改为独立无复位同步写进程，flags/mask保留异步复位。没有新增流水拍。仿真81项仅cache变化，物理139项只有cache及analysis.tcl变化；后者修正排队报告脚本，不放宽FDC。详见P5设计与验收口径.md及输入清单。

cache SHA256：`{result['source_cache_sha256']}`。

## 功能证据

5组逐拍、9种故障注入、6项本轮完整帧回归通过。定向58组/862沿，监测全部192项元数据；只调整初始化后门路径，原语义检查保留。六项均与R0核对完整规范化日志、输入/向量哈希、plusargs和输出周期。没有复用P4结果冒充P5。Icarus结果不等同于形式证明或ModelSim实跑。

真实压力摘要：

```text
{line}
```

模型fps基于125MHz假设，不是板端新帧发布率；cpp={cpp}，严格cpp≤2仍由二号处理。

## 物理证据与限制

进程状态：{run['state']}，exit={run['exit_code']}；起止UTC：{run['started_utc']} 至 {run['finished_utc']}。输入无漂移，未生成sbit。报告/日志和过程回执见results/physical_seed2及physical/host_seed2。

最终整机WNS：{wns if wns is not None else '无有效最终数值'}。缓存起点/终点定向判定：**{cache_verdict}**。定向报告由单独进程读取已完成数据库，若生成则覆盖四种setup/hold×slow/fast类型，并核对实际路径端点，不以全局摘要代替缓存结果。原始数据库、rtr、prr、CSV哈希保持不变。不能用中间日志、综合资源、没有报告到缓存路径，推断缓存125MHz通过。原有板级告警保留，UART自动位置不能作为接线依据。

综合cache行（若已生成）：

```text
{chr(10).join(resources) or '未生成'}
```

时间戳Feedback mux告警：{result['timestamp_feedback_warning_count']}。这是结构诊断计数，不代替最终时序。

停止判据及实际窗口证据见run_physical.py、P5设计与验收口径.md和process_receipt.json。受控停止与自然时序失败分别记录；未完成时不填写伪造WNS/TNS。

## 接收方

给二号协作者：候选工程、分组cache、完整功能/周期和物理证据，供缓存与core并行协作。给管理方：结果、输入身份和ZIP/Git校验清单归档。没有给执行方的烧录任务。

如果本方法未获得收敛，先向用户说明并询问是否继续寻找其他方法，不自行启动下一候选。完整资料存桌面ww；独立分支及草稿PR以外层上传回执为准，不合并main。
'''
(R/'审查结果与回传说明.md').write_text(text,encoding='utf-8')
(R/'README_当前进度.md').write_text('# P5本轮结果\n\n'+status+'；功能/周期验证通过。详见审查结果与回传说明.md。\n',encoding='utf-8')
dump(R/'results/evidence_audit.json',dict(passed=True,functional_passed=functional,physical_completed=completed,timing_passed=timing is True,
    candidate_inputs=81,physical_inputs=139,scope='Evidence integrity is distinct from timing acceptance'))
(W/'AB_P5_GitHub_PR正文_20261025.md').write_text(f'P5将192项缓存元数据分组写入并分离无复位数据进程，保持core/map、接口和可观察周期。5组逐拍、9种负例、6项完整帧回归及R0日志/周期对照通过。\n\n{status}。证据见工程内审查结果与回传说明.md、输入SHA清单及原生报告。未生成位流或上板；独立候选归档，不合并生产。核心调度/严格cpp≤2仍归二号。\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

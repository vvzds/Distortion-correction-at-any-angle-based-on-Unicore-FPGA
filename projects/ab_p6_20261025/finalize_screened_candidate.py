"""Archive an early-screen rejection without claiming full or timing acceptance."""
from pathlib import Path
import json,hashlib,shutil,datetime
R=Path(__file__).resolve().parent;W=R.parent;B=W/'AB_P6标签RAM与局部替换_20261025'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
gate=load(R/'results/synthesis_gate/result.json');run=load(R/'results/synthesis_gate/process_receipt.json')
eq=load(R/'results/equivalence_p6/summary.json');negative=load(R/'results/negative_checks_p6/summary.json')
assert run['state']=='FINISHED' and run['exit_code']==0
assert not run['changed_input_files'] and not run['bitstreams_present']
assert sha(R/'results/synthesis_gate/console.log')==run['console_sha256']
assert not gate['passed'] and not gate['gates']['ff_budget'] and gate['no_pnr_executed']
assert len(eq['results'])==5 and all(x['pass'] for x in eq['results'])
assert len(negative)==11 and all(x['detected'] for x in negative)
for item in eq['results']:
    d=R/'results/equivalence_p6'/item['case']
    assert sha(d/'simulation.log')==item['simulation_log_sha256']
    assert all(s['exit_code']==0 for s in item['steps'])
    assert item['inputs_before']==item['inputs_after']
    for f,h in item['inputs_after'].items():assert sha(R/f)==h
for item in negative:
    d=R/'results/negative_checks_p6'/item['mutation']
    assert item['compile_exit']==0 and item['simulation_exit']!=0
    assert sha(d/'mutant.v')==item['mutant_sha256']
    assert 'FATAL' in item['log'] and 'watchdog' not in item['log']
for file,base,key in [('candidate_identity.json','candidate','files'),('physical/input_identity.json','physical/host_seed2','inputs')]:
    for row in load(R/file)[key]:assert sha(R/base/row['file'])==row['sha256'],row['file']
assert sha(R/'candidate/source/rtl/undistort_core.v')=='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
assert not (R/'results/physical_seed2').exists() and not (R/'results/regression_p6').exists()
assert not list(R.rglob('*.sbit'))
ref=R/'reference_p6_initial';ref.mkdir(exist_ok=False)
for name in ('candidate_identity.json','physical/input_identity.json','candidate/source/rtl/undistort_cache_ab.v',
             'P6设计与筛选口径.md','results/synthesis_gate','results/equivalence_p6','results/negative_checks_p6'):
    p=B/name;q=ref/name;q.parent.mkdir(parents=True,exist_ok=True)
    if p.is_dir():shutil.copytree(p,q,ignore=shutil.ignore_patterns('*.vvp'))
    else:shutil.copy2(p,q)
for name in ('hdmi_ddr_ov5640_top.snr','hdmi_ddr_ov5640_top_syn.vm'):
    p=B/'physical/host_seed2/synthesize'/name;q=ref/'synthesize'/name;q.parent.mkdir(exist_ok=True);shutil.copy2(p,q)
dump(ref/'诊断勘误.json',dict(supersedes='results/synthesis_gate/netlist_overhead_analysis.json reason field',
    confirmed='Extra FF categories: age 192, leaf 96, winner age 12; exactly 300',
    not_established='Submodule boundary alone caused this; inlining retained all 300 extra FF',
    next_method_started=False))
shutil.copy2(W/'prepare_AB_P6_20261025.py',R/'prepare_initial_reference.py')
shutil.copy2(W/'prepare_AB_P6R1_20261025.py',R/'prepare_revision_reference.py')
result=dict(state='EARLY_GATE_FAILED_WAITING_USER_DIRECTION',source_complete=True,
    verification_passed=False,early_functional_passed=True,full_matrix_executed=False,
    completed_equivalence_cases=5,detected_negative_cases=11,resource_gate_passed=False,
    resource_gate=gate,physical_state='NOT_STARTED_RESOURCE_GATE_FAILED',physical_completed=False,
    timing_established=False,timing_passed=None,wns_ns=None,board_validated=False,new_bitstreams=[],
    cache_sha256=sha(R/'candidate/source/rtl/undistort_cache_ab.v'),core_unchanged=True,
    candidate_inputs_verified=len(load(R/'candidate_identity.json')['files']),
    physical_inputs_verified=len(load(R/'physical/input_identity.json')['inputs']),
    next_method_started=False,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
dump(R/'results/final_evidence_verification.json',result)
dump(R/'results/evidence_audit.json',dict(passed=True,meaning='Source and existing evidence integrity only; resource acceptance failed, no full regression or timing acceptance',
    source_complete=True,early_functional_passed=True,resource_gate_passed=False,timing_established=False))
note='''# P6 本轮审查结果：资源筛选未通过，等待下一方向确认

本轮没有取得缓存125MHz时序通过证据。P6首版和R1均完成5组逐拍及11种故障注入；随后只执行完整宿主的compile/synthesize/dev_map资源筛选，流程自然完成、exit0。FF门槛未过，因此没有运行六项完整帧矩阵、PNR、位流生成或板测。资源不合格不等于已证明物理时序必然失败。

| 缓存资源 | P4参考 | P6首版 | P6R1 |
|---|---:|---:|---:|
| LUT总量 | 16359 | 16865 | 16938 |
| 分布式RAM | 3168 | 3168 | 3168 |
| 逻辑LUT（总量减RAM） | 13191 | 13697 | 13770 |
| FF | 8268 | 8568 | 8568 |
| DRM | 8 | 8 | 8 |

运行前固定的门槛：标签RAM推断保留、分布式RAM≥95%、FF≤102%、逻辑LUT≤105%、DRM≤12。两版标签RAM/逻辑LUT/DRM通过，FF增加300（3.628447%），超过2%上限；没有事后放宽。

## 实现与诊断

从封存P4恢复tag_row/tag_seg原RAM写法，将年龄、done mask、Q_ELIG候选和Q_GROUP局部树放到同一局部组，原FSM拍数和全局12选1保持。R1只把局部子模块转换成原地命名generate块；完整22位声明、比较、写入均保留，F13覆盖序号最高位非零和极值。core/map/接口/输出周期、24KiB、FIFO512、lookahead256、125MHz、seed2、FDC/IP均不改。

综合网表计数确认新增300个FF来自：年龄192位、leaf年龄96位、winner年龄12位。此前“仅由子模块边界阻断常量传播导致”的解释被R1实测否定；去掉边界后这300位仍在，不能将初步猜测写成最终原因。原首版诊断另有勘误，保留历史记录。

P6R1与P4相比，逻辑LUT还增加579（约4.39%）。当前没有证据表明这种年龄/替换局部分组能弥补资源代价，故本轮停在筛选门槛，等待用户决定是否换方向。不是125MHz通过版，也不是自然PNR失败版。

## 证据入口

- `results/equivalence_p6/`：5组正式逐拍，定向58组、862沿、all-hit保持7拍。
- `results/negative_checks_p6/`：11种故障均由非超时FATAL检出，启动器要求正例先通过。
- `results/synthesis_gate/`：原始综合映射日志、输入前后SHA、预设门槛与实际资源表。
- `results/resource_overhead_audit.json`：最终综合GTP_DFF分类计数；不是早期Feedback mux告警数量。
- `physical/host_seed2/`：139项完整宿主输入及筛选输出；analysis.tcl保留固定seed2完整物理驱动，但本轮没有执行它。
- `candidate/`、`baseline/`、`tests/`：冻结核心、当前缓存、可复现验证及历史R0参考，参考不能当本轮完整帧结果。
- `reference_p6_initial/`：首版cache和原始证据，供复核差异。
- 名带`invalid_output_alias`的目录：R1转换初期output别名方向错误的无效试跑，已修正，禁止计入通过结论。
- `run_full_regression.py`、`run_physical.py`只是后续准备脚本，均被资源门槛阻挡，文件存在不代表已运行。

所有当前输入SHA已复核。核心调度/严格cpp≤2仍由二号负责；生产G4和main未改。

## 给谁

给二号协作者：完整候选、两版资源结果和逐拍证据，供缓存方向协作；不要求替换当前生产工程。

给管理方：本结果与校验清单归档，状态为资源筛选未通过、无最终时序。没有执行方烧录任务。

下一步建议转向标签读取/匹配及组选路网络的共享解码和扇出问题，先核查网表和定向时序依据，再决定是否实现；保持标签RAM、核心、接口和输出周期。此方向尚未启动，需用户确认。
'''
(R/'审查结果与回传说明.md').write_text(note,encoding='utf-8')
(R/'README_当前进度.md').write_text('# P6/P6R1资源筛选未通过\n\n先读[审查结果与回传说明](审查结果与回传说明.md)。已有5组逐拍和11种负例，FF门槛失败；无本轮全帧、PNR、WNS、位流和板级结论。等待用户确认下一方向。\n',encoding='utf-8')
(W/'AB_P6_GitHub_PR正文_20261025.md').write_text('P6保留标签RAM，将年龄与替换计算局部化；R1改为命名generate块，保持完整22位语义和冻结核心、接口、输出周期。两版5组逐拍和11种故障注入通过。\n\n资源筛选未通过：缓存FF8268→8568（+3.63%，预设上限+2%）；R1分布式RAM仍3168，逻辑LUT13191→13770。流程exit0，未执行完整帧矩阵、PNR、位流或板测。新增300 FF的分类已核对，但“仅子模块边界所致”被R1否定。\n\n归档源码、原始证据和诊断勘误，等待用户确认下一方向，不合并main。核心调度与cpp≤2继续由二号负责。\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='resource_gate'},indent=2))

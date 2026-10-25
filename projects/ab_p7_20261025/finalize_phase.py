"""Audit completed P7 stage, including failures, without inventing missing results."""
from pathlib import Path
import json,hashlib,datetime,subprocess,sys,shutil
R=Path(__file__).resolve().parent;W=R.parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
assert not (R/'DELIVERY_MANIFEST.json').exists(),'Already archived; preserve immutable evidence'
for file,base,key in [('candidate_identity.json','candidate','files'),('physical/input_identity.json','physical/host_seed2','inputs')]:
    for row in load(R/file)[key]:assert sha(R/base/row['file'])==row['sha256'],row['file']
cache=sha(R/'candidate/source/rtl/undistort_cache_ab.v')
assert sha(R/'candidate/source/rtl/undistort_core.v')=='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
eq=load(R/'results/equivalence_p7/summary.json')['results'];bank=load(R/'results/banks_p7/summary.json')['results']
assert len(eq)==5 and len(bank)==1 and all(x['pass'] for x in eq+bank)
for group,rows in [('equivalence_p7',eq),('banks_p7',bank)]:
    for row in rows:
        assert row['inputs_before']==row['inputs_after'] and all(s['exit_code']==0 for s in row['steps'])
        assert all(sha(R/f)==h for f,h in row['inputs_after'].items())
        assert sha(R/'results'/group/row['case']/'simulation.log')==row['simulation_log_sha256']
neg=load(R/'results/negative_checks_p7/summary.json');assert len(neg)==18 and all(x['detected'] for x in neg)
for row in neg:
    assert row['compile_exit']==0 and row['simulation_exit']!=0 and 'FATAL' in row['log'] and 'watchdog' not in row['log']
    assert sha(R/'results/negative_checks_p7'/row['mutation']/'mutant.v')==row['mutant_sha256']
gate=load(R/'results/synthesis_gate/result.json');syn=load(R/'results/synthesis_gate/process_receipt.json')
assert load(R/'results/archived_metrics_recheck.json')['passed']
for f,d in load(R/'reference_p4_resource/REFERENCE_MANIFEST.json')['files'].items():
    assert sha(R/'reference_p4_resource'/f)==d['sha256'],f
assert syn['state'] not in ('RUNNING','STARTING') and not syn['changed_input_files'] and not syn['bitstreams_present']
assert syn['console_sha256']==sha(R/'results/synthesis_gate/console.log')
assert syn['driver_sha256']==sha(R/'physical/host_seed2/synthesis_only.tcl')
reg_path=R/'results/regression_comparison.json';reg=load(reg_path) if reg_path.exists() else None
if (R/'results/regression_coordinator.json').exists():
    assert load(R/'results/regression_coordinator.json')['state']=='FINISHED'
full=bool(reg and reg['passed'] and len(reg['results'])==6)
run_path=R/'results/physical_seed2/process_receipt.json'
run=load(run_path) if run_path.exists() else None
if run:
    assert run['state'] not in ('RUNNING','STARTING') and not run['changed_input_files'] and not run['bitstreams_present']
    assert not run.get('owned_processes_remaining',[])
    assert run['console_sha256']==sha(R/'results/physical_seed2/console.log')
completed=bool(run and run['state']=='FINISHED' and run['exit_code']==0 and (R/'physical/host_seed2/report_timing/hdmi_ddr_ov5640_top.rtr').exists())
corners=[];wns=None;global_pass=None;cache_verdict='NOT_ESTABLISHED'
if completed:
    subprocess.run([sys.executable,'-B','-X','utf8',str(R/'inspect_physical.py')],check=True,stdout=subprocess.DEVNULL)
    phys=load(R/'results/physical_comparison.json');assert phys['candidate']['pnr_two_tables_match']
    corners=phys['candidate']['timing_summary'];assert len(corners)>=4
    global_pass=phys['all_reported_setup_hold_nonnegative']
    wns=min(x['worst_slack_ns'] for x in corners if x['kind']=='Setup')
    focused=load(R/'results/focused_timing.json');assert focused['original_evidence_unchanged']
    cache_verdict=focused['cache_closure']
    for name,item in focused['focused_reports'].items():
        assert sha(R/item['report'])==item['sha256'],name
    for file,digest in focused['original_inputs_after'].items():
        assert sha(R/file)==digest,file
    extra=load(R/'results/focused_diagnostic.json')
    assert extra['original_evidence_unchanged']
    for name,item in extra['focused_reports'].items():
        assert item['exit_code']==0 and not item['errors'] and item['all_selected_endpoints_match'] and item['four_check_corner_types_present'],name
        assert sha(R/item['report'])==item['sha256'],name
    for file,digest in extra['original_inputs_after'].items():
        assert sha(R/file)==digest,file
if run:subprocess.run([sys.executable,'-B','-X','utf8',str(R/'compare_warnings.py')],check=True,stdout=subprocess.DEVNULL)
assert not list(R.rglob('*.sbit'))
source_diag=W/'AB_标签读取比较诊断_20261025';diag=R/'diagnostics_before_p7'
assert not diag.exists()
shutil.copytree(source_diag,diag,ignore=shutil.ignore_patterns('*.vvp','__pycache__','*.pyc'))
shutil.copy2(W/'prepare_AB_P7_20261025.py',R/'prepare_candidate_reference.py')
status='资源/地址负载筛选未通过' if not gate['passed'] else ('功能与缓存受约束四角通过' if full and cache_verdict=='PASS_UNDER_EXISTING_CONSTRAINTS' else ('物理时序未闭合' if completed else '物理未完成，时序未建立'))
result=dict(state='COMPLETED_STAGE',source_complete=True,verification_passed=full,early_functional_passed=True,
    equivalence_cases=5,bank_public_allocation_slots=192,negative_cases=18,resource_gate_passed=gate['passed'],
    physical_state=run['state'] if run else 'NOT_STARTED_RESOURCE_GATE_FAILED',physical_completed=completed,
    timing_established=completed,system_reported_timing_passed=global_pass,wns_ns=wns,
    cache_focused_verdict=cache_verdict,cache_timing_passed=cache_verdict=='PASS_UNDER_EXISTING_CONSTRAINTS',
    acceptance_passed=bool(full and completed and cache_verdict=='PASS_UNDER_EXISTING_CONSTRAINTS'),
    source_cache_sha256=cache,candidate_inputs_verified=81,physical_inputs_verified=139,
    new_bitstreams=[],board_validated=False,next_method_started=False,status_zh=status,
    checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
dump(R/'results/final_evidence_verification.json',result)
dump(R/'results/evidence_audit.json',dict(passed=True,meaning='Evidence integrity, not functional/timing acceptance',source_complete=True,resource_gate_passed=gate['passed'],full_regression_passed=full,physical_completed=completed,acceptance_passed=result['acceptance_passed']))
base=gate['baseline_p4'];cur=gate['candidate']
text=f'''# P7标签RAM银行候选：{status}

用户选择当前最有依据的方案继续。独立候选从P4恢复，192槽标签改为12银行×16槽×16位，动态银行/本地地址写入；R1保留packed存储但恢复row/seg独立比较，以便共享公共比较逻辑；年龄、mask、替换树、四键和最高索引优先、FSM/接口/输出周期、冻结core/map、24KiB、FIFO512、lookahead256、125MHz、seed2、FDC/IP保留。

cache SHA256：`{cache}`。仿真81项仅cache变化；物理139项以input_identity为准，驱动不包含位流步骤。生产G4及main未替换。

## 已实际验证

原5组逐拍通过；新增192槽逐一公开分配、写入、取标签、加载和再次命中，并核对24种银行内重复优先级与2种全局重复优先级。强化定向468组/7318沿，all-hit7拍。18种故障注入均非超时FATAL检出，正例先通过才接受负例。

本轮完整六项回归：{'全部通过，并与R0输入/向量/plusargs/全日志/周期一致' if full else '没有取得完整六项通过结论，不能借用baseline中的历史结果'}。原始结果见results。首版P7的历史试跑与统计勘误独立保留；R1本轮全部重新验证，不借用首版结果。

## 综合与结构筛选

| cache资源 | P4 | P7 |
|---|---:|---:|
| LUT总量 | {base['LUT']} | {cur['LUT']} |
| 逻辑LUT | {base['logic_LUT']} | {cur['logic_LUT']} |
| FF | {base['FF']} | {cur['FF']} |
| 分布式RAM | {base['Distributed_RAM']} | {cur['Distributed_RAM']} |
| DRM | {base['DRM']} | {cur['DRM']} |

门槛结果：`{gate['passed']}`。逐项门槛、标签原语、银行及奇偶地址引脚负载见results/synthesis_gate/result.json和netlist_metrics.json。门槛运行前固定，减少物理RAM复制可以减少原语数量，但逻辑容量和全部银行RAM实现必须保留；没有放宽先前P6门槛。

引脚负载是cache局部综合网表计数，不是最终物理扇出或时序。标签读取到match的历史P2−1.558ns、88.231%布线延迟仅作诊断依据，保存在diagnostics_before_p7；不能冒称本候选时序。P4映射DB报告尝试被工具拒绝，原失败日志保留。

## 最终物理与验收边界

物理状态：`{result['physical_state']}`；物理完成：`{completed}`；整机受约束setup/hold报告通过：`{global_pass}`；最终setup WNS：`{wns}`；独立缓存from/to四角判定：`{cache_verdict}`。

只有完整矩阵通过且缓存from/to定向四角报告无负余量才判本阶段缓存目标通过。没有完整PNR报告时WNS为空；不得把资源或小测试通过当125MHz。物理停止策略固定seed2、最多7200秒、后期明显平台停机，过程证据保留。未生成位流、未板测，125MHz仿真模型fps不是实际新帧率。严格cpp≤2和核心/map继续由二号负责。

本轮进一步定向的标签匹配、年龄更新、组替换和最终选择路径及原生SHA核对见[P7R1瓶颈定位与后续选择](P7R1瓶颈定位与后续选择.md)，不能把标签匹配尚有的负余量写成已达标。

给二号协作者：候选源码和全部实测结果供缓存与核心协作；给管理方：报告和校验归档；没有执行方烧录任务。按用户最新要求，本轮仅基于已有G4把当前P7候选验证到能交接，不再索要或单独重发G4，不启动下一条优化路线；最终集成等待G7。完整候选验证工程按既有约定上传独立分支/草稿PR，不合并main。
'''
(R/'审查结果与回传说明.md').write_text(text,encoding='utf-8')
(R/'README_当前进度.md').write_text(f'# P7：{status}\n\n先读[审查结果与回传说明](审查结果与回传说明.md)。资源筛选={gate["passed"]}，完整六项回归={full}，缓存时序={cache_verdict}。无位流、无板测结论。\n',encoding='utf-8')
(W/'AB_P7_GitHub_PR正文_20261025.md').write_text(f'P7把192槽行/段标签合并到12个动态寻址RAM银行，保留冻结核心、年龄/替换机制、接口及输出周期，以减少并行标签读取的复制与地址负载。\n\n{status}。5组逐拍、192槽公开写读/取数/加载、重复命中优先级及18种故障注入通过；完整六项回归={full}；物理状态={result["physical_state"]}；缓存四角={cache_verdict}。实际资源和原生证据见工程报告。\n\n基于已有G4的P7交接验证工程；等待G7后再做最终集成。无位流/板测，不合并main。核心调度与严格cpp≤2继续由二号负责。\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

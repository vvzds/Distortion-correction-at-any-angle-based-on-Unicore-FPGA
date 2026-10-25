"""Final P5 receipt after the user ended this implementation, with partial coverage explicit."""
from pathlib import Path
import json,hashlib,re,datetime
R=Path(__file__).resolve().parent;W=R.parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
run=load(R/'results/physical_seed2/process_receipt.json');reg=load(R/'results/regression_controlled_status.json')
assert run['state']=='CONTROLLED_STOP_REQUESTED' and not run['owned_processes_remaining']
assert not run['changed_input_files'] and not run['bitstreams_present']
assert not load(R/'results/controlled_stop_regression.json').get('owned_processes_remaining',[])
assert sha(R/'results/physical_seed2/console.log')==run['console_sha256']
for section,root in [('candidate_identity.json',R/'candidate'),('physical/input_identity.json',R/'physical/host_seed2')]:
    obj=load(R/section)
    for row in obj.get('files',obj.get('inputs',[])):assert sha(root/row['file'])==row['sha256']
eq=load(R/'results/equivalence_p5/summary.json')['results'];neg=load(R/'results/negative_checks_p5/summary.json')
assert len(eq)==5 and all(x['pass'] for x in eq) and len(neg)==9 and all(x['detected'] for x in neg)
comparisons=[]
def normal(p):return [re.sub(rb'^.*?([^/\\]+\.v:\d+: \$finish called at)',rb'\1',s.strip()) for s in p.read_bytes().splitlines() if s.strip()]
for row in reg['cases']:
    if row['state']!='PASS':continue
    name=row['case'];b=R/'baseline/evidence'/name;c=R/'results/regression_p5'/name
    before=load(b/'inputs.json');after=load(c/'inputs.json')
    bi={x['file']:x['sha256'] for x in before['inputs']};ci={x['file']:x['sha256'] for x in after['inputs']}
    changed=[k for k in bi.keys()|ci.keys() if bi.get(k)!=ci.get(k)]
    assert changed==['source/rtl/undistort_cache_ab.v']
    assert before['plusargs']==after['plusargs'] and normal(b/'simulation.log')==normal(c/'simulation.log')
    assert load(c/'result.json')['inputs_unchanged']
    comparisons.append(dict(case=name,normalized_complete_log_equal=True,plusargs_equal=True,only_cache_changed=True))
dump(R/'results/completed_regression_comparison.json',dict(complete_matrix=False,completed_cases=comparisons,all_completed_cases_match=True))
counts={state:sum(x['state']==state for x in reg['cases']) for state in sorted({x['state'] for x in reg['cases']})}
result=dict(source_complete=True,verification_passed=False,verification_completed=False,directed_suites_passed=5,negative_checks_detected=9,
    regression_states=counts,completed_regressions_match_r0=True,physical_completed=False,timing_established=False,timing_passed=False,wns_ns=None,
    physical_state=run['state'],last_detailed_route=run['last_route'],board_validated=False,new_bitstreams=[],
    decision='User approved ending P5 and searching for another method',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
dump(R/'results/final_evidence_verification.json',result)
dump(R/'results/evidence_audit.json',dict(passed=True,scope='Source and existing evidence integrity only; NOT complete verification or timing acceptance',source_complete=True,
    candidate_inputs=81,physical_inputs=139,verification_completed=False,physical_completed=False,timing_passed=False))
text=f'''# P5结束记录：用户批准更换方法

**P5已结束，不作为125MHz合格候选。没有最终WNS/TNS，也不能断言它已经自然运行到时序失败。** 用户在看到综合资源代价与较差的中间布线进展后，明确批准“结束P5，继续寻找其他方法”。

P5的源码/IP/FDC/向量完整，81项仿真输入与139项物理输入经SHA核验无漂移；core/map/接口/输出周期未改。没有位流或上板。独立候选目录不覆盖生产版。

## 具体原因

原标签RAM被拆成寄存器：Distributed_RAM由3168降到32，FF由8268增到11640（+40.78%），逻辑LUT由13191增到16135（+22.32%）。Feedback mux告警消失并不代表净收益。原生证据及SHA见分组结构综合代价分析.md及results/synthesis_structure_comparison.json。

详细布线第37轮，P5未布通13489，P4同阶段11055。本轮按用户决定在详细布线{run['last_route'][0]}轮、尚有{run['last_route'][1]}条未布通连接时受控结束，早于自动停滞阈值，并非超时或自然完成。

## 已有与未完成的验证

5组逐拍和9种故障注入通过；完整回归当前状态：{counts}。identity、real_joint、legacy_sim三项已完成并与R0完整规范化日志、输入与参数逐项核对一致。integration、c6_real_subsystem运行中受控停止，c6_host_arb未运行，不能填写成通过，也不能将受控中断误认成语义失败。

完整矩阵状态见results/regression_controlled_status.json；完成项对照见results/completed_regression_comparison.json。真实压力已完成项仍为4161845拍、cpp2.007063，核心吞吐归二号。模型fps不代表板端实测。

物理与仿真进程均已核实结束；过程回执保存实际PID、父子关系、输入/日志哈希，临时盘符已清理。此前报告API验证读的是旧P2数据库，与P5时序无关。

## 后续与接收方

用户已授权寻找下一方法：优先保留标签RAM，将时间戳读取、eligible比较及组内替换选择一起局部化；先检查综合网表的存储形式、FF与逻辑代价，再决定是否投入完整物理验证。此方向不是已经实现或已经通过的结果。核心、接口及输出周期保持。

本包给二号协作者了解失败候选和资源证据、给管理方归档；不是给执行方的烧录包。完整工程按既有授权上传独立草稿PR，实际commit/URL以ww外层回执为准，不合并main。

`finalize_evidence.py`是要求完整矩阵通过后才能执行的原计划工具，本轮已取消，不要执行来覆盖本结束记录。
'''
(R/'审查结果与回传说明.md').write_text(text,encoding='utf-8')
(R/'README_当前进度.md').write_text('# P5已按用户决定结束\n\n5组逐拍、9种负例和3项完整回归通过，其余中断/未运行；物理未完成，无最终WNS。不是合格位流。详见审查结果与回传说明.md。\n',encoding='utf-8')
(W/'AB_P5_GitHub_PR正文_20261025.md').write_text('P5元数据写入分组改变了原标签存储的综合形式，FF增加40.78%、逻辑LUT增加22.32%，中间详细布线未优于P4。用户批准结束本候选并寻找其他方法。\n\n5组逐拍、9种负例、3项完整回归及R0日志/周期对照通过；另外2项回归中断、1项未运行。物理受控结束，无最终WNS/TNS，不声称125MHz通过或自然时序失败。完整源码/IP/FDC与实际已有证据归档；无位流、无板测，不合并生产。\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

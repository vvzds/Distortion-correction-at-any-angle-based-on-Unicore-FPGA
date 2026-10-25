"""Honest alternate report if current fixed-seed run ends without final timing."""
from pathlib import Path
import json, hashlib, re, datetime
N=Path(__file__).resolve().parent; R=N.parent; W=R.parent
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
run=load(R/'results/physical_seed2_resume_20261025/process_receipt.json')
assert run['state'] in ('FINISHED','TIMEOUT')
assert not run['changed_input_files'] and not run['bitstreams_present']
assert load(R/'results/regression_comparison_20261025.json')['passed']
audit=load(R/'results/evidence_audit_20261025.json'); assert audit['passed'] and not audit['physical_completed']
assert sha(R/'results/physical_seed2_resume_20261025/console.log')==run['console_sha256']
# Require a manually saved final process check; never archive mutable live output.
closed=load(R/'results/physical_seed2_resume_20261025/final_process_check.json')
assert closed['all_task_processes_stopped']
console=(R/'results/physical_seed2_resume_20261025/console.log').read_text(errors='replace')
routes=[(int(a),int(b)) for a,b in re.findall(r'Unrouted nets (\d+) at the end of iteration (\d+)',console)]
reg=load(R/'results/regression_comparison_20261025.json')
cpp_line=next(s for x in reg['results'] if x['case']=='real_joint' for s in x['candidate_summary'] if 'CORE PASS' in s)
cpp=float(re.search(r'cpp=([\d.]+)',cpp_line)[1])
info={'verification_passed':True,'physical_completed':False,'timing_passed':False,'timing_established':False,'cpp_passed':cpp<=2,'cpp':cpp,'wns_ns':None,'delta_vs_p1_ns':None,'physical_state':run['state'],'physical_exit_code':run['exit_code'],'route_last':routes[-1] if routes else None,'input_files_verified':{'candidate':81,'physical':139},'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(R/'results/incomplete_physical_review_20261025.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'results/final_evidence_verification_20261025.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
text=f'''# P4 本阶段结果与限制（2026-10-25）

**功能和周期验证通过；本轮物理运行未完成，不能确认125MHz时序达标。** 运行状态 `{run['state']}`，退出码 `{run['exit_code']}`；UTC起止 {run['started_utc']} 至 {run['finished_utc']}。末次已记录布线计数（未布通子网，迭代号）：`{routes[-1] if routes else None}`。没有最终WNS/TNS，不与P1最终数值作不等价比较，也不使用布局阶段slack作为最终结果。

## 已验证变更

P4 从 P3 出发，在已有 Q_SELECT 拍预计算行/段相等关系，Q_CHECK 四分支选择重复键的qid，保持原优先级和可见周期。保留P3时间戳冗余全局条件删除。缓存SHA `425ea5c734c174d0e4e08619d4ed8aebf96e95f60e8a60df9b2fcc010341fb49`；冻结core SHA `9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68`。只改缓存RTL；core/map、DDR、24KiB数据缓存、FIFO512、lookahead256、FDC/IP不变。

五组逐拍等价（定向58组、862沿）、七组负例、六项完整回归通过。四项沿用10月24日已通过且经SHA复核的结果，integration和c6_host_arb为10月25日新结果；完整规范化输出和周期与R0一致。81项候选和139项物理输入、运行日志及已生成原生报告均已核对SHA。旧中断输出保持不变。

真实压力摘要：

```text
{cpp_line}
```

cpp仍继承基线，严格cpp≤2问题归二号；模型fps是按125MHz假设计算，不是物理或板端证据。

## 物理证据与后续

固定seed2、125MHz、PDS2022.2-SP6.1 build138931（工具SHA `f22f86527d72ce7980dadad3adb189ee1d0271979d053e15d97da954b6848d0f`）、PG2L100H/FBG676/-6。未更换seed、降频或添加时序例外。当前缺少完整布线及最终四角报告，缓存及整机状态均为未确立通过。无sbit、无板测。原诊断UART及继承告警仍保留，自动布局位置不是板级接线依据。

过程详见 `results/physical_seed2_resume_20261025/console.log`、`process_receipt.json`、`final_process_check.json` 及 `results/evidence_audit_20261025.json`。审计PASS只说明材料身份及功能检查通过，不能解释为物理时序通过。

P4在用户授权转向分组元数据/局部译码路线后受控停止，原因及核实的目标进程见 `controlled_stop_for_authorized_structure_change.json`。这不是工具自然完成或超时退出。下一步建立独立结构候选，保持核心、接口和输出周期；若有证据表明该方法无效，先向用户说明并询问是否继续寻找其他方法，不自动转入下一种方案。二号接收完整工程、功能回归和物理未完成证据供协作；管理方按实际状态归档；执行方本轮没有烧录任务。核心调度/吞吐继续归二号。
'''
(R/'审查结果与回传说明_20261025.md').write_text(text,encoding='utf-8')
(R/'缓存时序与交付结论_20261025.md').write_text(text,encoding='utf-8')
(R/'README_当前进度.md').write_text('# P4本轮阶段结果（2026-10-25）\n\n功能/周期通过；物理未完成，无最终时序结论。见[本轮结果](审查结果与回传说明_20261025.md)。旧暂停记录只作历史溯源。复现入口在resume_20261025。\n',encoding='utf-8')
(W/'AB_P4_GitHub_PR正文_20261025.md').write_text('P4缓存候选完成5组逐拍等价、7组负例、6项完整回归，输出/周期与R0一致。core/map、DDR、FDC/IP和接口不变。\n\n本轮固定seed2物理运行未完成，无最终WNS/TNS，不能确认125MHz通过。保留原始日志、过程回执和输入/报告SHA。没有位流或板测，本PR用于独立候选复核归档，不合并生产基线。核心调度与吞吐继续由二号负责。\n',encoding='utf-8')
print(json.dumps(info,ensure_ascii=False,indent=2))

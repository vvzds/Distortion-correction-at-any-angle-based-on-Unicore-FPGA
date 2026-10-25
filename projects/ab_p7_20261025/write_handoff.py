from pathlib import Path
import json,hashlib,datetime
R=Path(__file__).resolve().parent

def load(p):return json.loads(p.read_text(encoding='utf-8'))
f=load(R/'results/final_evidence_verification.json')
assert f['state']=='COMPLETED_STAGE' and f['source_complete']
assert f['verification_passed'] and f['physical_completed'], 'P7 handoff requires completed full regression and PNR evidence'
assert load(R/'results/archived_metrics_recheck.json')['passed']
repo=load(R/'results/repository_review_identity.json')
for row in repo['copied_files']:
    assert hashlib.sha256((R/'repository_review'/row['file']).read_bytes()).hexdigest()==row['sha256']
assert not repo['current_p7_required_materials_missing']
reg=load(R/'results/regression_comparison.json')
assert len(reg['results'])==6 and reg['passed']
receipt=dict(state='READY_FOR_P7_HANDOFF_ON_EXISTING_G4',handoff_verification_complete=True,
    functional_regression_passed=True,full_regression_cases=6,resource_gate_passed=f['resource_gate_passed'],
    physical_completed=True,cache_125mhz_closed=f['cache_timing_passed'],system_timing_passed=f['system_reported_timing_passed'],
    system_setup_wns_ns=f['wns_ns'],production_accepted=False,g7_integrated=False,wait_for_final_g7=True,
    current_required_materials_missing=[],existing_g4_resend_required=False,
    source_cache_sha256=f['source_cache_sha256'],core_sha256='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68',
    repository_review_commit=repo['main_commit'],new_bitstreams=[],board_validated=False,
    checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(R/'results/handoff_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
text=f"""# P7交接说明：G4验证已完成，等待G7最终集成

接收方：二号协作者（缓存/核心整合）、管理方（阶段证据归档）。本轮没有执行方烧录任务。

## 结论与边界

本轮仅验证当前P7R1候选，不重发已有G4包、不启动新优化方法、不做G7最终集成。六项完整回归与R0的输入、向量、plusargs、规范化完整日志和周期一致；5组逐拍、192槽公开分配/写读/加载/再命中、24种局部和2种全局重复优先级、18负例均通过。资源筛选全部通过。

固定125MHz/seed2 PNR已自然完成，但整机slow setup WNS为{f['wns_ns']}ns，cache_from -0.971ns、cache_to -1.273ns；标签匹配 -0.114ns、年龄更新 -1.273ns、组内替换 -0.971ns、最终替换选择 -0.044ns。map定向 -1.035ns。当前P7能交接源码和有效证据，不能判125MHz通过、不能生产晋升、不能推算实板30新帧/s。

本轮与P4综合对照：cache LUT总16359→14919（-8.80%），逻辑LUT13191→13255（+0.49%），FF8268不变、DRM8不变；标签RAM3136→1632，qa/qb局部引脚负载1752/1753→985/984。P4无完成的最终PNR时序，不能把历史P2数值称为同条件P4时序收益。

## 二号从哪里接

- 候选cache：candidate/source/rtl/undistort_cache_ab.v，SHA256 `{f['source_cache_sha256']}`。
- 完整G4 A+B验证载体：physical/host_seed2/ab_seed2_analysis.pds；脚本入口analysis.tcl，冻结139项设计/IP/FDC/驱动输入见physical/input_identity.json。复跑前另复制工作目录，保留归档报告原件。未生成位流。
- 功能与输入对应：results/regression_comparison.json、results/regression_p7、candidate_identity.json。独立Icarus执行，不冒称本机ModelSim结果。
- 原生时序：physical/host_seed2/report_timing与place_route；cache_from/cache_to/map四角定向报告见results/focused_timing；细分诊断见results/focused_diagnostic。原PNR DB/报告SHA前后不变。
- 具体瓶颈：P7R1瓶颈定位与后续选择.md。prep_ptr读地址与touch分发两段长线合计4.834ns；跨core/cache的边界在文中标明，未单方面修改core。
- P4综合原件与复核工具：reference_p4_resource和recheck_archived_metrics.py；首版P7的失败/别名统计勘误单独保存在reference_p7_initial，不混作R1结果。

当前core/map、外部接口和输出周期保持既有A+B验证版本。FIFO512/lookahead256/24KiB/192槽奇偶机制仍在，core SHA为9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68。P7相对P4仅cache改变。

不能把P7缓存文件直接改名替换仓库根目录undistort_line_cache。根目录原核与本轮A+B的lookup/touch/retire/分段统计及FIFO组织不同；最终G7接入需按明确目标提交核对对应关系和生命周期。

## 管理方归档

先读审查结果与回传说明.md及results/handoff_receipt.json，再核对results/final_evidence_verification.json。证据完整、功能通过和时序闭合是独立字段；本轮是P7阶段交接，不是整机验收。完整离线ZIP另有包外SHA/CRC和逐文件清单；GitHub上传到独立分支和草稿PR，不合并main。

## 后续资料与独立评估规则

当前P7交接必需资料缺件：无。G4已有，不需要用户重发。

本轮直接读取仓库main `{repo['main_commit']}` 的1469项文件目录、12个分支引用，以及5个collab2分支目录；已获得G7历史登记/回执/分片清单、现有G4静态工程和板端记录的引用。结果在repository_review，不把历史G7候选、根目录空hook或不同map哈希当成最终G7整机。

等最终G7目标提交明确后，先从仓库获取其源码/清单/报告，独立核对core/map/cache/bilinear、宿主/FDC/IP、参数格式、坐标方向和统计语义，再做适配与重验。只在仓库仍不能确定最终版本选择、需改变冻结接口口径或需要实板操作时向用户确认。无需再请其他协作者替本轮做可独立完成的评估。

交接后的下一状态是等待G7最终集成，不继续自动开新缓存优化路线。静态矫正、core调度和严格cpp≤2仍由二号负责。
"""
(R/'交接说明_二号与管理方.md').write_text(text,encoding='utf-8')
p=R/'README_当前进度.md';p.write_text('# P7阶段交接已就绪；125MHz尚未闭合\n\n先读[交接说明](交接说明_二号与管理方.md)与[审查结果](审查结果与回传说明.md)。基于已有G4完成本轮验证，等待G7最终集成。没有位流或板测通过结论。\n',encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))

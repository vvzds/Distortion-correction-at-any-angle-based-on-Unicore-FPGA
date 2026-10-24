"""Record a controlled incomplete PNR attempt without inventing final slack."""
from pathlib import Path
import json,hashlib,re,datetime
R=Path(__file__).resolve().parent
def load(rel):return json.loads((R/rel).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
run=load('results/physical_seed2/process_receipt.json')
assert run['state']=='FINISHED' and run['exit_code']!=0
assert not run['changed_input_files'] and not run['bitstreams_present']
assert sha(R/'results/physical_seed2/console.log')==run['console_sha256']
assert load('results/regression_comparison.json')['passed']
assert len(load('results/regression_p3/summary.json')['results'])==6
assert all(x['passed'] for x in load('results/regression_p3/summary.json')['results'])
assert all(x['pass'] for x in load('results/equivalence_p3/summary.json')['results'])
assert all(x['detected'] for x in load('results/negative_checks_p3/summary.json'))
for row in load('candidate_identity.json')['files']:assert sha(R/'candidate'/row['file'])==row['sha256']
for row in load('physical/input_identity.json')['inputs']:assert sha(R/'physical/host_seed2'/row['file'])==row['sha256']
stop=load('results/physical_seed2/controlled_stop.json')
stop['completion']={'method':'PowerShell Stop-Process for the verified task parent 36444 and PDS child 40196',
                    'powershell_exit_code':0,'verified_processes_absent':True,
                    'actual_process_exit_code':run['exit_code'],'finished_utc':run['finished_utc'],
                    'note':'taskkill first returned Access denied; native Stop-Process then succeeded. Original failed attempt is retained above.'}
(R/'results/physical_seed2/controlled_stop.json').write_text(json.dumps(stop,ensure_ascii=False,indent=2),encoding='utf-8')
body=(R/'results/physical_seed2/console.log').read_text(errors='replace').split('Total 69393 subnets.')[-1]
rows=[(int(m[2]),int(m[1])) for m in re.finditer(r'Unrouted nets (\d+) at the end of iteration (\d+)',body)]
assert rows and rows[-1][1]>0
final=R/'physical/host_seed2/report_timing/hdmi_ddr_ov5640_top.rtr'
assert not final.exists(), 'Do not describe an existing final report as absent'
report=f'''# P3阶段归档：功能通过，物理尝试未完成

**五组逐拍对照、五种故障注入、六项完整回归通过；125MHz物理收敛未验证。** 固定seed2的PDS详细布线长时间未完成，本轮受控停止。没有最终WNS/TNS、最终PNR资源表或四角报告，不给出伪造的最终时序数值，不晋升生产。

## 变更与范围

从P1删除last_use更新循环外层冗余alloc/DONE/touch条件，保持逐槽条件和优先级。唯一RTL变更为cache，SHA256 `614797ccd5a2f122caed1050fc013e28e3852f14923b3a037fa7c5d453a65330`。core/map/bilinear、可见周期、DDR、FDC/IP及缓存24KiB/FIFO512/lookahead256保持原样。用户明确核心和吞吐由二号负责。

## 功能证据

五组R0/P3逐拍检查PASS，定向58组862沿，40次完成77次分配2次等待，全命中7沿。五种负例均检出。identity、real_joint、legacy_sim、integration、c6_real_subsystem、c6_host_arb全部PASS，六份完整规范化日志、参数、像素和周期均与R0一致；运行输入哈希未变。

真实参数压力场景为2073600像素零误差、4161845拍、cpp=2.007063。125MHz假设下计算fps=30.034756，不能当作已达成的物理频率或板端发布率。严格cpp≤2的差距保留给二号处理。

## 停止原因及原始证据

PDS版本2022.2-SP6.1 build138931，原工具/125MHz/seed2不变。物理运行UTC {run['started_utc']} 至 {run['finished_utc']}。详细布线第417轮曾降到405条未完成连接；发出停止请求时第713轮仍有638条，最近100轮范围524至734，连续296轮未改善最小值。最终保存的最后日志为第{rows[-1][0]}轮、{rows[-1][1]}条未完成连接。此处表示本轮未收敛即被停止，不等于证明工具继续运行必然失败。

第一次taskkill因Access denied未执行成功；随后核对本任务两个PDS进程后用PowerShell Stop-Process成功停止，已复查进程消失。包装器正常保存非零退出码、释放SUBST、核验139项输入未变化，无位流。见results/physical_seed2/controlled_stop.json、process_receipt.json和console.log。

综合报告仍可查：缓存16451 LUT、8266 FF、8 DRM；这是综合阶段数值，不能代替最终PNR结果。综合网表分析发现触碰逻辑跨层合并，不能将原i_touch端口消失解释成真实触碰路径消失。辅助map/cache-from/cache-to报告尚未运行，不能据其缺失判通过。

## 交付与续接

保留完整工程输入、有限验证、所有原始中间产物和受控停止记录，作为未采用候选归档。P4已将稳定键比较提前到已有Q_SELECT拍，继续针对P1原生done_mask负路径核验。用户要求本次P4阶段收尾后暂停，不再启动下一轮。

当前没有P3运行中的仿真/PDS，没有烧录或生产合并。完整项目按既有授权上传隔离分支/草稿PR，实际地址以ww上传回执为准；归档不代表125MHz通过。P3中旧续接脚本及成功路径报告脚本仅为历史流程工具，不能无条件直接重跑；重现须使用干净副本和新的输出目录。
'''
(R/'审查结果与回传说明.md').write_text(report,encoding='utf-8')
(R/'README_当前进度.md').write_text('# P3已归档，未采用\n\n功能、周期六项回归均通过；详细布线停滞后受控停止，没有最终时序结论。不能标为125MHz通过。详见审查结果与回传说明.md。P3无运行任务；P4阶段收尾后按用户要求暂停。\n',encoding='utf-8')
(R/'当前运行与续接.md').write_text('# P3运行已结束\n\n历史会话96636、46703均已结束。P3完整回归及日志比较通过，物理尝试受控停止；原95025/2699/74454等待器均已停止。当前P4回归42306、物理/后处理83566运行中，以ww/本轮完成后暂停_20261024.md和最终当前续接文件为准。不要执行旧等待脚本启动重复任务。\n',encoding='utf-8')
out={'verification_passed':True,'physical_status':'CONTROLLED_STOP_UNCONVERGED','timing_passed':False,'timing_verdict':'NOT_ESTABLISHED','final_wns_ns':None,'input_files_verified':{'candidate':81,'physical':139},'core_throughput_owner':'collaborator02','timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(R/'results/final_evidence_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))

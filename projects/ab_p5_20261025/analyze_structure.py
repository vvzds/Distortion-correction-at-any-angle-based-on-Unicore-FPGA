"""Compare emitted synthesis structures; no claim about final timing from area alone."""
from pathlib import Path
import json,re,hashlib
R=Path(__file__).resolve().parent;W=R.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
records={}
for version,root in [('P4',W/'AB_P4缓存实施_20261024/physical/host_seed2_resume_20261025'),('P5',R/'physical/host_seed2')]:
    p=root/'synthesize/hdmi_ddr_ov5640_top.snr';text=p.read_text(errors='replace')
    line=next(s for s in text.splitlines() if '+ u_cache ' in s);cols=[x.strip() for x in line.split('|')]
    values={k:float(cols[i+2]) for i,k in enumerate(['LUT','FF','Distributed_RAM','APM','DRM'])}
    values['logic_LUT']=values['LUT']-values['Distributed_RAM']
    records[version]=dict(report=str(p),sha256=sha(p),cache=values,raw_row=line)
delta={k:records['P5']['cache'][k]-records['P4']['cache'][k] for k in records['P5']['cache']}
percent={k:100*delta[k]/records['P4']['cache'][k] for k in delta if records['P4']['cache'][k]}
out=dict(versions=records,delta=delta,delta_percent=percent,
    interpretation='Tag distributed RAM replaced by small bank register storage; feedback-mux warning disappearance alone did not establish net area or timing improvement. Final fixed-seed routing evidence remains decisive.')
(R/'results/synthesis_structure_comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'分组结构综合代价分析.md').write_text(f'''# P5结构代价：已验证的中间发现

P4/P5原生综合报告逐项核对：

| 缓存指标 | P4 | P5 | 变化 |
| --- | --- | --- | --- |
| LUT总量 | {records['P4']['cache']['LUT']:g} | {records['P5']['cache']['LUT']:g} | {delta['LUT']:+g} |
| Distributed_RAM | {records['P4']['cache']['Distributed_RAM']:g} | {records['P5']['cache']['Distributed_RAM']:g} | {delta['Distributed_RAM']:+g} |
| LUT总量减Distributed_RAM | {records['P4']['cache']['logic_LUT']:g} | {records['P5']['cache']['logic_LUT']:g} | {percent['logic_LUT']:+.2f}% |
| FF | {records['P4']['cache']['FF']:g} | {records['P5']['cache']['FF']:g} | {percent['FF']:+.2f}% |
| DRM | {records['P4']['cache']['DRM']:g} | {records['P5']['cache']['DRM']:g} | {delta['DRM']:+g} |

原P4综合日志明确推断tag_row/tag_seg为RAM；P5每个8槽模块把row/seg/age保存为本地寄存器。原P4综合网表的last_use也已经存在GTP_DFF_E及CE，因此不能把早期Feedback mux告警数直接当作最终新增LUT数。P5告警归零是真的，电路整体变小或125MHz成功则尚未由此得到证明。

P5仍保留全相联标签读取、192项eligible比较及替换树。仅改变元数据写入分组，并没有把这些读/比较/替换网络一起局部化；不能将文件中的模块分组直接解释为物理布局已经局部化。

同阶段详细布线迭代37：P4未布通11055，P5未布通13489。该观察属于中间进展，不能证明最终必然失败。最终继续按事先记录的固定seed2、收敛门槛及有效四角报告决定；若当前方法不能达到目标，先问用户是否继续找其他方法，不自行换方案。

证据路径、SHA与原始cache表行见results/synthesis_structure_comparison.json。报告均为本机PDS实跑，不是估计数。
''',encoding='utf-8')
print(json.dumps(dict(cache_P4=records['P4']['cache'],cache_P5=records['P5']['cache'],delta_percent=percent),indent=2))

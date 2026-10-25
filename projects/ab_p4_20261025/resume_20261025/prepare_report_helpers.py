"""Prepare report helpers for new run locations, preserving old interrupted receipts."""
from pathlib import Path
N=Path(__file__).resolve().parent;R=N.parent
s=(R/'write_final_report.py').read_text(encoding='utf-8')
s=s.replace('R=Path(__file__).resolve().parent','R=Path(__file__).resolve().parent.parent')
s=s.replace('physical/host_seed2','physical/host_seed2_resume_20261025').replace('results/physical_seed2','results/physical_seed2_resume_20261025')
for stem in ['physical_comparison','regression_comparison','focused_timing','final_evidence_verification']:
    s=s.replace(stem+'.json',stem+'_20261025.json')
# The prior P1 report remains the unchanged historical file.
s=s.replace("prior_p1/physical_comparison_20261025.json","prior_p1/physical_comparison.json")
s=s.replace('contributor-01/ab-p4-20261024','contributor-01/ab-p4-20261025').replace('projects/ab_p4_20261024','projects/ab_p4_20261025')
s=s.replace("R/'审查结果与回传说明.md'","R/'审查结果与回传说明_20261025.md'")
s=s.replace('identity、real_joint、legacy_sim、integration、c6_real_subsystem、c6_host_arb六项通过，参数、规范化完整日志和周期与R0一致。',
'''identity、real_joint、legacy_sim、c6_real_subsystem复用10月24日已通过结果，源码及编译/仿真日志SHA在恢复时复核通过；integration和c6_host_arb使用10月25日新输出重跑。六项参数、规范化完整日志和周期与R0一致。旧中断结果保留，不改写为PASS。''')
s=s.replace('整个任务尚未全部达标','当前阶段尚未全部达标')
s=s.replace('P1/P2原包不变。','P1/P2/P3原包不变。P4旧暂停快照与中断物理输出保留，新物理宿主只从139项清单复制输入，未使用旧运行标记冒充本轮证据。')
(N/'write_final_report.py').write_text(s,encoding='utf-8')
print('Fresh-run final report helper prepared; not executed')

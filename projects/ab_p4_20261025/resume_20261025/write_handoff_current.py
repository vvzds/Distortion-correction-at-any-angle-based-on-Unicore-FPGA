"""Write handoff from actual final evidence, with no automatic cache-pass claim."""
from pathlib import Path
import json
N=Path(__file__).resolve().parent; R=N.parent; W=R.parent
def load(p): return json.loads(p.read_text(encoding='utf-8'))
v=load(R/'results/final_evidence_verification_20261025.json')
a=load(R/'results/evidence_audit_20261025.json'); assert a['passed']
t=load(R/'results/cache_timing_review_20261025.json')
p=load(R/'results/physical_comparison_20261025.json')['candidate']
assert v['verification_passed']
neg=t['negative_cache_paths']
cache=('未通过' if neg else '尚不能确认通过；须人工核验定向对象覆盖')
table=['| 报告 | 起点 | 终点 | 类型 | Slack/ns |','| --- | --- | --- | --- | --- |']
for row in neg[:8]: table.append(f'| {row["report"]} | `{row["start"]}` | `{row["end"]}` | {row["type"]} | {row["slack_ns"]:+.3f} |')
src=['| 报告 | 实际路径数 | 路径端点匹配过滤 | 路径类型 |','| --- | --- | --- | --- |']
for row in t['report_sources']:
    src.append(f'| {row["name"]} | {row.get("paths_reported",0)} | {row.get("selection_matches",False)} | {", ".join(row.get("cache_types",[]))} |')
text=f'''# P4 缓存时序与交付结论（2026-10-25）

本轮阶段性验证已完成。缓存路径结论：**{cache}**。整机最终 DDR 慢角 Setup WNS 为 **{v['wns_ns']:+.3f}ns**，相对 P1 变化 **{v['delta_vs_p1_ns']:+.3f}ns**（正值改善）；整机四角判据{'通过' if v['timing_passed'] else '未通过'}。不是125MHz上板验收通过版本。

五组逐拍等价、七组负例及六项完整回归通过；六项完整规范化输出和周期与 R0 一致。四项复用10月24日已通过日志，两项10月25日续验，输入/日志/最终报告SHA已经审计。旧中断输出保持原状。

## 原生缓存路径证据

以下结果取自实际路径块，不使用过滤报告内可能保留的整机摘要推断缓存结论。任何一条受约束负 slack 缓存路径均足以判为未通过；若没有负路径，也仍需确认 get_cells 选择覆盖后才可认定通过。

{chr(10).join(src)}

{chr(10).join(table) if neg else '当前发出的路径中没有发现负 slack 缓存路径；这不等同于完整覆盖已成立。'}

详细路径、报告SHA及类型覆盖见 `results/cache_timing_review_20261025.json`。完整资源、四角 Setup/Hold、TNS、失败端点和告警见 `审查结果与回传说明_20261025.md`、`results/physical_comparison_20261025.json`、`results/warning_comparison_20261025.json`。

## 给谁、怎么用

- **二号协作者**：完整 P4 工程、变更说明、原生时序及六项回归证据，供缓存与核心接口协作复核。冻结的 core/map、接口和周期不变；核心调度与 cpp≤2 吞吐继续归二号，本轮未接管或重构核心。
- **管理方**：本轮结果、输入和报告哈希审计、交付包校验回执。按实际时序状态归档，不登记为整机已达标。
- **执行方/板端操作者**：本轮无位流、无烧录指令；不要用该离线诊断宿主替代已验证生产工程。原 UART 自动布局位置不能当作接线约束。

全部输出在桌面 ww，完整ZIP位于 `待转交/AB_P4缓存优化_源码与验证_20261025.zip`。GitHub按既有授权上传独立分支/草稿PR，实际提交与链接以 ww 的上传回执和交付索引为准，未合并 main。

## 本阶段收尾

按此前要求完成本阶段后保存并暂停，不启动 P5，不生成位流或上板。下一次从本轮最终报告定位缓存关键路径继续；禁止用降频、换seed或修改时序例外掩盖未通过项。仿真 cpp={v['cpp']} 是继承基线值，125MHz假设下的模型fps不是板端新帧发布率。
'''
(R/'缓存时序与交付结论_20261025.md').write_text(text,encoding='utf-8')
body=f'''P4 在已有 Q_SELECT 拍预计算行/段相等关系，简化 Q_CHECK 重复键选择，并保留 P3 时间戳冗余条件删除。冻结 core/map、DDR、FDC/IP、24KiB 数据缓存、FIFO512、lookahead256 和可观察周期未改变。

验证：5组逐拍等价、7组负例、6项完整回归通过；完整输出/周期与R0一致，输入和日志SHA审计通过。10月25日补完两项续验和固定seed2最终物理检查，旧中断记录保留。

实际整机慢角Setup WNS={v['wns_ns']:+.3f}ns，125MHz整机{'报告通过' if v['timing_passed'] else '时序未通过'}；缓存{cache}。cpp={v['cpp']}，核心吞吐仍归二号。原生报告、告警、资源和覆盖限制均在工程目录。本PR用于独立候选复核归档，没有位流或板测，不合并生产基线。
'''
(W/'AB_P4_GitHub_PR正文_20261025.md').write_text(body,encoding='utf-8')
print(json.dumps({'cache':cache,'whole_system_passed':v['timing_passed'],'wns_ns':v['wns_ns'],'recipients':['collaborator02','management'],'no_bitstream':True},ensure_ascii=False,indent=2))

from pathlib import Path
import json,hashlib,shutil,datetime
W=Path(r'C:\Users\lenovo\Desktop\ww');B=W/'AB_P8触摸译码局部化_20261025';R=W/'AB_P8_FF5物理验证_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
assert not R.exists()
manifest=load(B/'DELIVERY_MANIFEST.json')
assert all(sha(B/row['file'])==row['sha256'] for row in manifest)
R.mkdir()
for row in manifest:
    p=B/row['file'];q=R/row['file'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
# Keep the original stage snapshot/receipt separate from this new experiment.
H=R/'prior_early_stage';H.mkdir()
for n in ('DELIVERY_MANIFEST.json','P8阶段结果与下一步选择.md','README_当前进度.md'):
    shutil.copy2(B/n,H/n)
gate=load(R/'results/synthesis_gate/result.json')
assert not gate['passed'] and [k for k,v in gate['gates'].items() if not v]==['ff_budget']
assert gate['candidate']['FF']<=gate['baseline_p4']['FF']*1.05
updated=dict(gate['gates']);updated['ff_budget']=gate['candidate']['FF']<=gate['baseline_p4']['FF']*1.05
assert all(updated.values())
auth=dict(passed=True,authorization='User explicitly selected: 允许 +5% 试验预算，完成一次布线（推荐）',authorized_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 scope='One fixed 125MHz/seed2 PNR experiment for unchanged P8. FF ratio to P4 only: 1.02 -> 1.05. Other gates, core, interfaces, output cycles, FDC and IP unchanged. Preserve original failed gate.',
 original_gate_sha256=sha(R/'results/synthesis_gate/result.json'),original_gate_passed=False,original_ff_ratio_limit=1.02,experiment_ff_ratio_limit=1.05,
 experiment_ff_integer_limit=int(gate['baseline_p4']['FF']*1.05),candidate_ff=gate['candidate']['FF'],experiment_gates=updated,
 source_archive=str(B),source_manifest_sha256=sha(B/'DELIVERY_MANIFEST.json'),source_cache_sha256=sha(B/'candidate/source/rtl/undistort_cache_ab.v'),
 no_rtl_changes=True,no_constraint_changes=True,no_bitstream=True)
(R/'results/ff5_experiment_authorization.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2),encoding='utf-8')
p=R/'run_physical.py';s=p.read_text(encoding='utf-8')
old="assert json.loads((R/'results/synthesis_gate/result.json').read_text())['passed'], 'Resource gate failed'"
new="""authorization=json.loads((R/'results/ff5_experiment_authorization.json').read_text(encoding='utf-8'))
assert authorization['passed'] and authorization['experiment_ff_ratio_limit']==1.05
assert all(authorization['experiment_gates'].values())
assert sha(R/'results/synthesis_gate/result.json')==authorization['original_gate_sha256']
assert not json.loads((R/'results/synthesis_gate/result.json').read_text())['passed'], 'Original early FAIL must stay preserved'
assert authorization['source_cache_sha256']==sha(R/'candidate/source/rtl/undistort_cache_ab.v')
assert json.loads((R/'results/touch_exhaustive_retry/result.json').read_text())['passed']"""
assert s.count(old)==1;s=s.replace(old,new)
s=s.replace("provisional_overlap=True,acceptance_requires_full_regression_comparison=True,","provisional_overlap=False,diagnostic_only=True,acceptance_requires_full_regression_comparison=True,\n    experiment_authorization_sha256=sha(R/'results/ff5_experiment_authorization.json'),")
s=s.replace("scope='Same 125MHz seed2 offline candidate; original FDC/IP; no bitstream or board claim'","scope='Authorized P8 FF+5% single 125MHz seed2 physical experiment; P8 RTL and original FDC/IP unchanged; not production acceptance or bitstream'")
p.write_text(s,encoding='utf-8')
for n in ('run_focused_reports.py','run_focused_diagnostic.py'):
    p=R/n;s=p.read_text(encoding='utf-8').replace('completed P7','completed P8 FF5').replace('completed P7R1','completed P8 FF5');p.write_text(s,encoding='utf-8')
readme='''# P8 FF+5%单次物理试验正在进行

用户已明确批准仅将本次FF试验预算从P4的+2%变为+5%，完成一次125MHz/seed2布局布线。P8 RTL不改，核心/接口/输出周期/其它资源门槛/原FDC/IP不变。旧P8目录和ZIP保持归档。

原+2%早筛仍为FAIL，见results/synthesis_gate/result.json；本次试验许可与单独筛选见results/ff5_experiment_authorization.json。没有把原早筛改成PASS。

先完整PNR，再对cache_from/cache_to/map及age/tag/victim分别只读导出四种corner/check的STA。物理结果与P7R1相同seed和约束比较；新结果不冒充六项完整帧回归或板验。当前不生成位流/烧录，不自动开启第二个seed或新候选。
'''
(R/'README_当前进度.md').write_text(readme,encoding='utf-8')
shutil.copy2(__file__,R/'prepare_p8_ff5.py')
entry=f'''# 2026-10-25：P8 FF+5%单次物理验证已获准

用户明确批准“允许 +5% 试验预算，完成一次布线”。新隔离目录：{R}。

保留旧P8、P7归档及原+2%早筛FAIL。只对不改RTL的P8试验放宽FF预算到+5%，其余门槛/核心/接口/输出周期/FDC/IP保持。运行run_physical.py，完成后run_focused_reports.py与run_focused_diagnostic.py，并用P7R1同条件报告对照。只一个125MHz/seed2，不生成位流，不自动开下一路线。

当前先检查results/physical_seed2/process_receipt.json和工具会话，避免重复运行。完整六项回归尚未执行；已有小矩阵和2752组穷举证据已从P8按SHA复制。结果完成后保存新ZIP并更新独立草稿PR。
'''
(W/'P8当前续接_20261025.md').write_text(entry,encoding='utf-8')
cwd=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m')/'当前任务续接.md';cwd.write_text(entry+'\n---\n\n'+cwd.read_text(encoding='utf-8'),encoding='utf-8')
print(json.dumps(dict(root=str(R),authorization=auth),ensure_ascii=False,indent=2))

"""Archive audited P4 evidence and stage reproducible Git inputs; no push or merge."""
from pathlib import Path
import json, hashlib, zipfile, shutil, datetime, sys
N=Path(__file__).resolve().parent; R=N.parent; W=R.parent
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert load(N/'collection_summary.json')['state'] in ('COLLECTED','REVIEW_REQUIRED')
assert load(R/'results/evidence_audit_20261025.json')['passed']
assert load(R/'results/final_evidence_verification_20261025.json')['verification_passed']
assert (R/'缓存时序与交付结论_20261025.md').is_file()
receipt=load(R/'results/physical_seed2_resume_20261025/process_receipt.json')
assert receipt['state'] in ('FINISHED','TIMEOUT')
assert load(R/'results/evidence_audit_20261025.json')['physical_completed'] or (R/'results/incomplete_physical_review_20261025.json').is_file()
assert not receipt['changed_input_files'] and not receipt['bitstreams_present']

out=W/'待转交'; out.mkdir(exist_ok=True)
z=out/'AB_P4缓存优化_源码与验证_20261025.zip'
G=W/'GitHub_AB_P4_20261025'; D=G/'projects/ab_p4_20261025'
m=R/'DELIVERY_MANIFEST_20261025.json'
stage_only='--stage-only' in sys.argv
if stage_only:
    assert G.is_dir() and (G/'.git').exists() and not D.exists()
    prior=load(out/'AB_P4交付包校验回执_20261025.json')
    assert sha(z)==prior['sha256']
    manifest=load(m); files=[R/x['file'] for x in manifest]+[m]
    for row in manifest: assert sha(R/row['file'])==row['sha256'],row['file']
else:
    assert not z.exists(), 'Do not overwrite delivery'
    files=sorted(p for p in R.rglob('*') if p.is_file() and p.suffix not in ('.vvp','.pyc') and '__pycache__' not in p.parts and p.name!='DELIVERY_MANIFEST_20261025.json')
    assert not any(any(x in p.relative_to(R).parts for x in ('.git','.local','github-cli-auth')) for p in files)
    manifest=[{'file':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    m.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'); files.append(m)
    with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as f:
        for p in sorted(files): f.write(p,R.name+'/'+p.relative_to(R).as_posix())
with zipfile.ZipFile(z) as f:
    assert f.testzip() is None
    for row in manifest: assert hashlib.sha256(f.read(R.name+'/'+row['file'])).hexdigest()==row['sha256'],row['file']

result={'archive':str(z),'bytes':z.stat().st_size,'sha256':sha(z),'file_count':len(files),'verified_manifest_entries':len(manifest),'verified_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sent_or_uploaded':False}
receipt_path=out/'AB_P4交付包校验回执_20261025.json'
if not stage_only:
    receipt_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(0)

inputs={x['file'] for x in load(R/'physical/input_identity.json')['inputs']}
copied=[]; omitted=[]
for p in sorted(files):
    rel=p.relative_to(R); name=rel.as_posix()
    if name=='DELIVERY_MANIFEST_20261025.json': continue
    if name.startswith('physical/host_seed2/') or name.startswith('physical/host_seed2_resume_20261025/'):
        hostrel='/'.join(name.split('/')[2:])
        evidence=p.suffix in ('.snr','.dmr','.prr','.rtr','.csv','.log','.pds') or 'timing_summary_after_hold_fix' in p.name
        if hostrel not in inputs and not evidence:
            omitted.append({'file':name,'reason':'regenerable PDS database/netlist; retained in offline ZIP'}); continue
    assert p.stat().st_size<95*1024*1024, ('Git file too large',name)
    q=D/rel; q.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,q)
    copied.append({'file':name,'bytes':q.stat().st_size,'sha256':sha(q)})
assert all((D/'physical/host_seed2_resume_20261025'/x).is_file() for x in inputs)
(D/'GIT_MANIFEST.json').write_text(json.dumps({'source':str(R),'copied_files':copied,'omitted_regenerable_files':omitted,'physical_inputs_complete':len(inputs),'offline_archive':z.name,'offline_sha256':sha(z)},ensure_ascii=False,indent=2),encoding='utf-8')
(D/'.gitattributes').write_text('# Preserve archived input and evidence bytes.\n** -text\n',encoding='utf-8')
(D/'.gitignore').write_text('__pycache__/\n*.pyc\n*.vvp\n/physical/host_seed2*/compile/\n/physical/host_seed2*/*/*.adf\n',encoding='utf-8')
(D/'README.md').write_text('''# A+B P4 缓存优化候选（2026-10-25）

先读[实际结果](审查结果与回传说明_20261025.md)及[缓存时序与交付结论](缓存时序与交付结论_20261025.md)。这是独立候选工程与证据归档，验收状态以本轮最终原生报告为准。

- `physical/host_seed2_resume_20261025/`：本轮完整 PDS 宿主、139项源码/IP/FDC/工程输入及本轮已生成报告；物理完成状态见实际结果。运行入口为 `analysis.tcl`，固定 seed2、125MHz，没有位流。
- `candidate/`、`tests/`：冻结核心、候选缓存、仿真依赖和完整帧向量。
- `resume_20261025/`：本轮复现入口、审计与报告工具。[复现说明](resume_20261025/复现说明_20261025.md)说明四项旧结果和两项续验的来源。
- `results/`：五组逐拍等价、七组负例、六项完整回归、物理与告警证据。
- `physical/host_seed2/`、暂停记录及旧脚本是历史中断证据。不要把旧 FAIL 改写为 PASS，也不要执行旧脚本覆盖新结果。
- `baseline/`、`prior_p1/`：R0/P1 对照证据。
- `GIT_MANIFEST.json`：字节/SHA清单及省略的可再生成 PDS 数据库；原始工程输入齐全。完整离线产物在桌面 ww/待转交。

本轮只修改缓存，core/map、DDR、FDC/IP 与外部可观察周期未改。core 调度及吞吐仍归二号。没有生产合并、位流或板测；模型 fps 不是板端实测。UART 自动分配位置不能作为板卡接线依据。请在副本中用新输出路径复跑。
''',encoding='utf-8')
result.update(git_project=str(D),git_copied_files=len(copied),git_omitted_regenerable=len(omitted),physical_inputs_complete=len(inputs))
receipt_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))

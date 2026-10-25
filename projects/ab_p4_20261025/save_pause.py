"""Save a verified pause snapshot; no restart, build, test, or publication."""
from pathlib import Path
import json,hashlib,datetime,zipfile
R=Path(__file__).resolve().parent;W=R.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(rel):return json.loads((R/rel).read_text(encoding='utf-8'))
expected='425ea5c734c174d0e4e08619d4ed8aebf96e95f60e8a60df9b2fcc010341fb49'
assert sha(R/'candidate/source/rtl/undistort_cache_ab.v')==expected
for x in load('candidate_identity.json')['files']:assert sha(R/'candidate'/x['file'])==x['sha256']
for x in load('physical/input_identity.json')['inputs']:assert sha(R/'physical/host_seed2'/x['file'])==x['sha256']
reg=load('results/regression_p4/summary.json')['results']
passed=[x['case'] for x in reg if x['passed']]
pending=[x['case'] for x in reg if not x['passed']]
assert set(passed)=={'identity','real_joint','legacy_sim','c6_real_subsystem'}
assert set(pending)=={'integration','c6_host_arb'}
assert all(not load(f'results/regression_p4/{name}/result.json')['bad_tokens'] for name in pending)
phys=load('results/physical_seed2/process_receipt.json')
assert phys['state']=='FINISHED' and phys['exit_code']!=0 and not phys['changed_input_files']
assert not phys['bitstreams_present']
assert sha(R/'results/physical_seed2/console.log')==phys['console_sha256']
assert all(x['pass'] for x in load('results/equivalence_p4/summary.json')['results'])
assert all(x['detected'] for x in load('results/negative_checks_p4/summary.json'))
out={'status':'PAUSED_BY_USER','saved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
     'source_sha256':expected,'candidate_inputs_verified':81,'physical_inputs_verified':139,
     'equivalence_passed':5,'negative_mutations_detected':7,'complete_regression_passed':passed,
     'regression_interrupted_by_user':pending,'physical_status':'INTERRUPTED_BY_USER_DURING_DETAILED_ROUTING',
     'final_timing_verdict':'NOT_ESTABLISHED','task_processes_verified_stopped':True,'task_subst_drives_released':True,
     'raw_result_note':'Raw runner labels aborted cases passed=false and emits FAIL because they did not finish. Retain raw records; classify as user interruption, not an observed functional mismatch.'}
(R/'results/pause_summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
doc=f'''# 已暂停：P4缓存优化续接记录

用户最新指令为“保存下来下次继续”，已立即停止运行；此前“完成当前阶段后暂停”已被这条立即暂停指令替代。暂停UTC时间：{out['saved_utc']}。本任务没有继续运行的仿真/PDS或等待器，临时SUBST已释放。

## 已保存内容

- P4工程：桌面ww/AB_P4缓存实施_20261024。cache SHA256：`{expected}`；81项候选输入、139项物理输入已重新校验。
- 唯一RTL变化仍是cache：在已有Q_SELECT拍保存行/段相等标志，Q_CHECK静态选择，沿用P3冗余条件删除。core/map、接口、输出拍数、DDR/FDC/IP保持。
- 五组逐拍对照PASS，七种故障注入均检出。
- 完整回归已PASS：identity、real_joint、legacy_sim、c6_real_subsystem。真实压力仍4161845拍，2073600像素零误差，cpp=2.007063。
- integration、c6_host_arb因用户暂停被中断；原始runner的FAIL/非零退出表示未完成，未发现FATAL或像素错配。integration保存到I5 frame5/frame6已通过；宿主仲裁保存到518400字进度。
- P4 PDS已完成综合、布局、全局布线，开始详细布线后被用户暂停；原始进程回执、日志、数据库全部保留。没有最终WNS/TNS、四角报告或位流，125MHz尚未确认。综合缓存16359 LUT、8268 FF、8 DRM仅为综合资源值。
- 原始中断证据在results/user_pause_request.json、results/pause_summary.json及physical_seed2/process_receipt.json，输入未变。

## 下次从这里继续

1. 先核对本cache SHA和现有输入清单。若源码不变，复用上述四项已完成回归；只重跑integration、c6_host_arb到新输出目录，不覆盖本次中断日志。若再改RTL，原验证不能冒充新源码的通过证据。
2. 为P4建立新的物理运行副本，仅复制physical/input_identity.json列出的139项输入；保持同一PDS版本、125MHz和seed2，不覆盖已有物理数据库。按新目录适配run_physical.py的输出位置并重新执行；不要直接在原目录重跑prepare_physical.py。
3. 两项回归结束后汇总六项证据，与R0完整日志/像素/周期核对；比较脚本需指向新结果，保留四项已通过的原始身份。原summary里的两项中断不改写成PASS。
4. 核对最终未过滤report_timing和CSV，以及cache-from/cache-to匹配路径和四角覆盖；空/失败辅助报告不能判通过。完成后写真实阶段结论、打包和按既有授权上传完整工程。
5. 不直接启动旧continue_after_p3_physical.py：P3已受控停止，没有其期待的最终报告。旧continue_current.py和现有run_physical.py默认输出目录已存在，必须为新运行适配目录。不要启动重复任务。

用户确认一号仅做缓存125MHz，核心调度和吞吐由二号负责。缺失资料先查仓库，不混用新版核心。所有后续工程/文档/回执继续放桌面ww。当前处于暂停，等用户明确“继续”再恢复；未启动P5。

## P3已完成归档

P3五组逐拍、五负例、六完整回归及规范化日志/周期比较通过；详细布线停滞后受控停止，无最终时序。完整ZIP已在ww/待转交：AB_P3缓存优化_源码与验证_20261024.zip（SHA256 `9b82a635d11dcb9ee66e5d4455f4d0a635bbb0b0a7b5705484929ca308cceb65`）。

P3已按授权上传草稿PR https://github.com/vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA/pull/4 ，提交`51f3245154c604182e67d1ba694921f2cb5d608f`，393文件核验，未合并main。详见ww/AB_P3交付索引_20261024.md。P4当前仅保存暂停快照，尚未作为完成交付上传。
'''
(R/'暂停续接.md').write_text(doc,encoding='utf-8')
(R/'README_当前进度.md').write_text('# P4已按用户要求暂停\n\n五组逐拍、七项负例通过；四项完整回归通过，两项用户中断。物理流程在详细布线开始后暂停，无最终时序结论。看暂停续接.md和results/pause_summary.json。所有本任务进程已停止，不自动开始下一轮。\n',encoding='utf-8')
(W/'本轮完成后暂停_20261024.md').write_text('# 最新要求：立即暂停，已执行\n\n用户后续明确“保存下来下次继续”，已立即停止P4仿真和PDS，不再等待当前阶段完成。准确状态及续接步骤见 AB_P4缓存实施_20261024/暂停续接.md。P3已归档上传；P4为未完成的暂停快照，不声称125MHz通过。\n',encoding='utf-8')
main=W/'当前续接_20261024.md'
old=main.read_text(encoding='utf-8')
main.write_text('# 最新：用户要求立即暂停，P4已保存并停机\n\n'+doc+'\n\n---\n\n以下为历史记录，以本页最新暂停状态为准。\n\n'+old,encoding='utf-8')
# Snapshot every saved file, including partial databases and simulator executables.
files=sorted(p for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='PAUSE_MANIFEST.json')
manifest=[{'file':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
m=R/'PAUSE_MANIFEST.json';m.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');files.append(m)
dest=W/'暂停快照';dest.mkdir(exist_ok=True)
z=dest/'AB_P4缓存优化_暂停快照_20261024.zip';assert not z.exists()
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as f:
    for p in files:f.write(p,R.name+'/'+p.relative_to(R).as_posix())
with zipfile.ZipFile(z) as f:
    assert f.testzip() is None
    for row in manifest:assert hashlib.sha256(f.read(R.name+'/'+row['file'])).hexdigest()==row['sha256']
receipt={'archive':str(z),'bytes':z.stat().st_size,'sha256':sha(z),'files':len(files),'verified_entries':len(manifest),'status':'PAUSED_SNAPSHOT_NOT_ACCEPTED_DELIVERY'}
(dest/'AB_P4暂停快照校验回执_20261024.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(receipt,ensure_ascii=False,indent=2))

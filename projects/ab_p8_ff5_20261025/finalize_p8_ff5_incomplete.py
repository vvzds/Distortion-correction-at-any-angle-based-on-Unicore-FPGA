from pathlib import Path
import json,hashlib,zipfile,shutil,re,datetime
W=Path(r'C:\Users\lenovo\Desktop\ww');R=W/'AB_P8_FF5物理验证_20261025';P7=W/'AB_P7R1标签RAM与共享比较_20261025';P8=W/'AB_P8触摸译码局部化_20261025'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
first=load(R/'results/physical_seed2/process_receipt.json');run=load(R/'results/physical_resume/process_receipt.json')
assert first['state']=='CONTROLLED_STOP_ROUTE_PLATEAU' and run['state']=='CONTROLLED_STOP_WALL_LIMIT'
assert load(R/'results/post_resume_coordinator.json')['state']=='NO_COMPLETE_PHYSICAL_DATABASE'
assert not (R/'DELIVERY_MANIFEST.json').exists()
for receipt in (first,run):assert not receipt['changed_input_files'] and not receipt['bitstreams_present'] and not receipt['owned_processes_remaining']
for old in (P7,P8):assert all(sha(old/row['file'])==row['sha256'] for row in load(old/'DELIVERY_MANIFEST.json'))
rows=load(R/'candidate_identity.json')['files'];assert len(rows)==81 and all(sha(R/'candidate'/r['file'])==r['sha256'] for r in rows)
rows=load(R/'physical/input_identity.json')['inputs'];assert len(rows)==139 and all(sha(R/'physical/host_seed2'/r['file'])==r['sha256'] for r in rows)
assert sha(R/'candidate/source/rtl/undistort_core.v')=='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
auth=load(R/'results/ff5_experiment_authorization.json');gate=load(R/'results/synthesis_gate/result.json')
assert not gate['passed'] and sha(R/'results/synthesis_gate/result.json')==auth['original_gate_sha256'] and auth['passed']
assert sha(R/'candidate/source/rtl/undistort_cache_ab.v')==auth['source_cache_sha256']
assert not (R/'physical/host_seed2/place_route/hdmi_ddr_ov5640_top_pnr.adf').exists()
assert not (R/'results/focused_timing.json').exists() and not (R/'results/p7r1_p8_ff5_comparison.json').exists()
route_rows={}
for name in ('physical_seed2','physical_resume'):
    p=R/'results'/name/'console.log';body=p.read_text(errors='replace')
    detailed=[dict(iteration=int(i),unrouted=int(n)) for n,i in re.findall(r'^        Unrouted nets (\d+) at the end of iteration (\d+)\.',body,re.M)]
    assert detailed
    route_rows[name]=dict(log_sha256=sha(p),detailed_iterations=len(detailed),last=detailed[-1],best=min(detailed,key=lambda x:x['unrouted']),trajectory=detailed,
        error_lines=[s for s in body.splitlines() if s.startswith('E:')],
        error_interpretation='Flow-0189 appears after runner termination; not independent evidence of spontaneous tool crash')
resume=route_rows['physical_resume']
assert resume['last']==dict(iteration=728,unrouted=286)
checkpoint=R/'physical/host_seed2/place_route/hdmi_ddr_ov5640_top_plc.adf'
basis=load(R/'results/route_resume_basis.json')
assert sha(checkpoint)==basis['checkpoint_sha256']
native=load(R/'results/synthesis_gate/native_identity.json')
assert all(sha(R/'results/synthesis_gate/native'/n)==h for n,h in native.items())
snr=R/'physical/host_seed2/synthesize/hdmi_ddr_ov5640_top.snr'
line=next(s for s in snr.read_text(errors='replace').splitlines() if '+ u_cache ' in s);cols=[s.strip() for s in line.split('|')]
stats={k:float(cols[i+2]) for i,k in enumerate(['LUT','FF','Distributed_RAM','APM','DRM'])}
assert all(stats[k]==gate['candidate'][k] for k in stats)
(R/'results/route_trajectory_and_diagnosis.json').write_text(json.dumps(dict(attempts=route_rows,placed_checkpoint_sha256=sha(checkpoint),placed_checkpoint_unchanged=True,synthesis_cache_resources=stats,
 original_synthesis_native_unchanged=True,conclusion='Incomplete routing under the configured execution limits. No completed timing database; no valid post-route WNS. Cannot establish timing gain or claim that P8 is fundamentally unroutable.'),indent=2),encoding='utf-8')
summary=f'''# P8 FF+5%物理试验：路由未完成，无有效WNS

本轮已执行用户批准的P8、125MHz/seed2、FF+5%诊断试验，但未在配置执行时限内完成详细路由。没有可用的最终WNS，不能判断P8比P7R1更快，也不能判为125MHz通过。当前可交接首选仍为P7R1。

## 授权与输入保持

用户明确选择“允许 +5% 试验预算，完成一次布线”。只对该P8试验把缓存FF相对P4的上限从+2%改为+5%，其它门槛、核心、接口、输出周期、1080p30及FDC/IP保持。原+2%早筛仍FAIL，原P8/P7归档和逐SHA清单均复核不变。

cache SHA256：`{auth['source_cache_sha256']}`；核心SHA256：`9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68`。81项候选、139项原物理输入前后哈希一致。综合缓存LUT15394、逻辑LUT13730、FF8568、分布式RAM1664、DRM8；与原P8相同。FF+3.63%在本次+5%试验预算内，其余原资源门槛通过。

## 实际执行：两段工具调用均保留

1. 完整流程完成综合、映射、布局、全局路由。详细路由到161轮/1700条未连线时，被旧启动器继承的停滞启发式主动结束。对照窗口最佳未连线1627→1592，改善约2.15%，低于启发式5%阈值。这是受控停止，不应把末尾Flow-0189误写为独立工具崩溃。
2. 为完成授权，查询PDS本机help pnr，确认input_place_db_file支持保存布局输入。从同一布局检查点重启路由，保留原map DB/125MHz/seed2/RTL/FDC/IP，取消停滞启发式，只保留7200秒硬时限。没有重新综合或重新布局；没有保存部分路由，所以是从已布局起点重跑路由，不是从161轮继续。两次调用不冒称一次连续自然完成。

第二段最后到728轮/286条未连线，实际回执计时{run['elapsed_s']:.1f}秒，触发CONTROLLED_STOP_WALL_LIMIT。最少曾到{resume['best']['unrouted']}条（第{resume['best']['iteration']}轮），但随后反复，未归零。原place_route/*.prr为空；只有plc布局检查点，没有pnr完整路由数据库。两个停止动作后本轮进程均已结束，subst已清理。

## 对问题的定位和局限

P8保留局部touch边界的综合效果已确认，但详细路由末段反复，说明本次映射/布局需要较长时间处理拥塞/连接冲突。不能仅凭这些未连线计数确认具体某个RTL网络造成冲突，也不能据此断言该算法或器件永远不可布通。当前没有完成的物理数据库，不能提供cache_from/cache_to/map或年龄更新的最终STA收益。

P7R1原已完成的slow setup WNS=-1.273ns是旧版本数据，不套给P8。布局阶段估计slack也不替代最终WNS。读报告等待器已正确记录NO_COMPLETE_PHYSICAL_DATABASE并未导出误导性时序报告。

前阶段功能小矩阵仍可复用：五组逐拍、192槽公开写读/优先级、22负例、2752组touch穷举均通过；本次RTL未改变。没有跑本候选六项完整帧回归，没有位流/烧录/板验/G7最终集成。

## 建议与下一步边界

不建议继续对同一P8强保留组合边界做无期限重复路由。P8比P7多300个年龄MSB FF、475 LUT，目前没有实测时序收益支撑保留此代价。建议结束P8路线，保留P7R1作为当前可交接缓存；待仓库中G7唯一基线明确后，核对其复用命中/预取控制，优先处理已确认的跨core/cache长路径，再决定下一实现。用户要求方法无前景先询问，本轮不会自动换seed、加新流水、改core或开新候选。

若仍希望继续P8，需要单独确认延长执行预算或调整物理策略；当前不把这项确认解释为已授权。已保存完整源码、IP/约束输入、两个路由回执与轨迹、布局检查点、综合网表和原始日志，可供二号独立复核，无需重发G4。

## 转交对象

- 二号：完整工程、布局检查点和路由轨迹，用于G7接入前核对，不是可烧录位流。
- 管理方：本说明、FF+5%许可、原早筛FAIL及两段受控停止回执，记录“路由未完成，无WNS，未晋升”。
- 执行方：本轮没有需烧录的文件。

证据入口：results/ff5_experiment_authorization.json、results/physical_seed2/process_receipt.json、results/physical_resume/process_receipt.json、results/route_resume_basis.json及results/route_trajectory_and_diagnosis.json。
'''
(R/'P8_FF5物理结果与交接说明.md').write_text(summary,encoding='utf-8')
(R/'README_当前进度.md').write_text('# P8 FF+5%试验已结束：路由未完成，无WNS\n\n第二段从保存布局重启路由，在7200秒硬时限/728轮时仍286条未连线，已受控停止。不是工具自然布线完成，不是时序PASS，也不能据此判定绝对不可布通。当前首选仍P7R1。\n\n详见P8_FF5物理结果与交接说明.md；原+2%早筛FAIL、用户+5%许可、两段工具调用和原日志均保留。没有位流/板测。下一路线待用户决定。\n',encoding='utf-8')
receipt=dict(state='COMPLETED_EXPERIMENT_WITH_INCOMPLETE_ROUTE',physical_completed=False,route_complete=False,valid_post_route_wns_available=False,cache_closure='NOT_EVALUABLE_NO_COMPLETED_ROUTE',
 original_ff_gate_failed=True,authorized_ff5_resource_gate_passed=True,source_complete=True,preferred_handoff_candidate='P7R1',
 attempts=[dict(name='full_flow',state=first['state'],last_iteration=161,last_unrouted=1700),dict(name='same_placed_checkpoint_route',state=run['state'],last_iteration=728,last_unrouted=286,best=resume['best'])],
 original_inputs_unchanged=True,archives_p7_p8_unchanged=True,core_unchanged=True,constraints_unchanged=True,ips_unchanged=True,
 cache_sha256=auth['source_cache_sha256'],full_frame_regression_executed=False,bitstream_generated=False,board_tested=False,
 next_route_requires_decision=True,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(R/'results/final_physical_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
entry=f'''# P8 FF+5%本轮已结束：路由未完成，无有效WNS

目录：{R}。用户授权的+5%固定125MHz/seed2试验已执行，两次工具调用：首次详细路由161轮被继承停滞启发式结束；同保存布局检查点重启后取消该启发式，728轮/286条未连线时触及7200秒硬时限，受控停止。

没有完整PNR数据库、最终WNS或定向STA收益；不能宣布125MHz通过或P8绝对不可布通。原+2%早筛FAIL保留，本次+5%资源门槛通过。RTL、core、接口、周期/FDC/IP无改动，81/139输入及P7/P8归档SHA不变。本轮进程已结束，无subst；无新位流/板测。

当前可交接首选仍P7R1。建议结束P8强保留局部touch路线，等G7明确基线后核对跨core/cache控制路径。未获下一选择不自动延长预算、换seed、改流水/core或开候选。完整结果见P8_FF5物理结果与交接说明.md；交付ZIP在ww/待转交，GitHub草稿PR #9将更新本结果。
'''
(W/'P8当前续接_20261025.md').write_text(entry,encoding='utf-8')
cwd=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m')/'当前任务续接.md';cwd.write_text(entry+'\n---\n\n'+cwd.read_text(encoding='utf-8'),encoding='utf-8')
shutil.copy2(__file__,R/'finalize_p8_ff5_incomplete.py')
shutil.copy2(Path(__file__).parent/'run_p8_ff5_resume_reports.py',R/'run_p8_ff5_resume_reports.py')
files=[]
for p in sorted(R.rglob('*')):
    if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.vvp') and p.name!='DELIVERY_MANIFEST.json':files.append(dict(file=p.relative_to(R).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
(R/'DELIVERY_MANIFEST.json').write_text(json.dumps(files,ensure_ascii=False,indent=2),encoding='utf-8')
archive=W/'待转交/给二号与管理方_AB_P8_FF5路由未完成记录_20261025.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for row in files:z.write(R/row['file'],'P8_FF5/'+row['file'])
    z.write(R/'DELIVERY_MANIFEST.json','P8_FF5/DELIVERY_MANIFEST.json')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and len(z.namelist())==len(files)+1
    for row in files:assert hashlib.sha256(z.read('P8_FF5/'+row['file'])).hexdigest()==row['sha256']
out=dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,file_count=len(files)+1,all_crcs_passed=True,all_file_sha256_passed=True,physical_stage=receipt)
(W/'待转交/AB_P8_FF5交付包校验回执_20261025.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))

from pathlib import Path
import json,hashlib,shutil,datetime
W=Path(r'C:\Users\lenovo\Desktop\ww');R=W/'AB_P8_FF5物理验证_20261025';P=R/'physical/host_seed2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
run=json.loads((R/'results/physical_seed2/process_receipt.json').read_text(encoding='utf-8'))
assert run['state']=='CONTROLLED_STOP_ROUTE_PLATEAU' and not run['changed_input_files'] and not run['owned_processes_remaining']
assert run['plateau_evidence']['previous_best']==1627 and run['plateau_evidence']['latest_best']==1592
A=R/'results/stopped_first_route';A.mkdir(exist_ok=False)
for name in ('place_route','multiseed_summary.csv','run.log','flow.log','impl.tcl'):
    a=P/name
    if a.is_dir():shutil.copytree(a,A/name)
    elif a.exists():shutil.copy2(a,A/name)
checkpoint=P/'place_route/hdmi_ddr_ov5640_top_plc.adf';assert checkpoint.stat().st_size>0
mapped=P/'device_map/hdmi_ddr_ov5640_top_map.adf';assert mapped.stat().st_size>0
record=dict(reason='First runner inherited a 20-vs-20 iteration plateau heuristic. It stopped the route at iteration161 before completion, causing downstream Flow-0189. Correcting this execution limitation to finish the user-authorized experiment from its saved placed checkpoint.',
 no_new_rtl=True,no_new_seed=True,no_new_frequency=True,no_new_constraint=True,no_new_placement_requested=True,
 checkpoint_sha256=sha(checkpoint),mapped_sha256=sha(mapped),first_attempt_receipt_sha256=sha(R/'results/physical_seed2/process_receipt.json'),
 next_scope='Continue routing from saved placement using original map DB; disable inherited plateau termination; keep 7200s hard wall and explicit cancellation.',
 replay_disclosure='Partial routing was not checkpointed. Routing restarts from the saved placement, not from route iteration161. Preserve both invocations; do not claim uninterrupted natural completion or independent second seed.')
(R/'results/route_resume_basis.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
tcl='''set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
pnr -input_db_file {Q:/device_map/hdmi_ddr_ov5640_top_map.adf} -input_place_db_file {Q:/place_route/hdmi_ddr_ov5640_top_plc.adf} -gplace_seed 2 -groute_seed 2
report_timing -max_path 20 -nworst 1
exit
'''
# Q: is reserved only for this sequential run, after the previous mapping was removed.
assert not Path('Q:/').exists()
(P/'resume_route.tcl').write_text(tcl,encoding='utf-8')
s=(R/'run_physical.py').read_text(encoding='utf-8')
s=s.replace("O=R/'results/physical_seed2'","O=R/'results/physical_resume'")
start=s.index('# Preserve the early native artifacts')
end=s.index('O.mkdir(parents=True,exist_ok=False)',start)
s=s[:start]+s[end:]
s=s.replace("drive=next(c+':' for c in 'QRSTUVWXY' if not Path(c+':/').exists())","drive='Q:';assert not Path('Q:/').exists()")
s=s.replace("'-file',drive+'/analysis.tcl'","'-file',drive+'/resume_route.tcl'")
s=s.replace('if latest>=1000 and latest>=previous*0.95:', 'if False:  # Disabled inherited heuristic; finish this fixed-seed diagnostic route.')
s=s.replace("stop_policy=dict(max_wall_seconds=7200,plateau_min_iteration=80,window_iterations=20,\n                     minimum_unrouted=1000,required_best_improvement_fraction=0.05)","stop_policy=dict(max_wall_seconds=7200,plateau_stop_enabled=False),\n    resume_basis_sha256=sha(R/'results/route_resume_basis.json'),placed_checkpoint_sha256=sha(P/'place_route/hdmi_ddr_ov5640_top_plc.adf')")
(R/'run_route_resume.py').write_text(s,encoding='utf-8')
for name in ('run_focused_reports.py','run_focused_diagnostic.py'):
    p=R/name;s=p.read_text(encoding='utf-8').replace("results/physical_seed2/process_receipt.json","results/physical_resume/process_receipt.json");p.write_text(s,encoding='utf-8')
p=Path(__file__).parent/'compare_p8_ff5.py';s=p.read_text(encoding='utf-8').replace("results/physical_seed2/process_receipt.json","results/physical_resume/process_receipt.json");p.write_text(s,encoding='utf-8')
shutil.copy2(__file__,R/'prepare_p8_route_resume.py')
print(json.dumps(record,indent=2))

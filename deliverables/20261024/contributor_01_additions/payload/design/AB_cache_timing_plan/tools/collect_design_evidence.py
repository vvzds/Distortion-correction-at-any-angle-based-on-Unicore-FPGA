"""Read-only evidence extraction and abstract design checks; no RTL or PDS runs."""
from pathlib import Path
import hashlib,json,itertools,re,shutil
ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT.parent/'audit_delivery_20261024'
RUN=AUDIT/'runs/ab_seed2_inputs'
WS=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m')
TEST=WS/'outputs/G4_AB_R1_R4_复验接收_20261023/execution/candidate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(rel,obj):
 p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
manifest={r['path']:r for r in json.loads((AUDIT/'files_sha256.json').read_text(encoding='utf-8'))}
sources=[]
def copy_verified(p,rel):
 identity=p.relative_to(AUDIT).as_posix()
 expected=manifest[identity]
 if sha(p)!=expected['sha256'] or p.stat().st_size!=expected['bytes']:raise ValueError('source identity mismatch: '+identity)
 d=ROOT/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d)
 if sha(d)!=expected['sha256']:raise ValueError('copy mismatch')
 sources.append({'source':str(p),'package_path':rel,'bytes':p.stat().st_size,'sha256':sha(p),'verified_against_prior_delivery_manifest':True})
for n in ['undistort_cache_ab.v','undistort_core.v','undistort_map.v','undistort_bilinear.v']:
 copy_verified(RUN/'source/rtl'/n,'reference/frozen_rtl/'+n)
for p,rel in [
 (RUN/'HDMI_DDR3_OV5640_test.fdc','reference/frozen_fdc/HDMI_DDR3_OV5640_test.fdc'),
 (RUN/'report_timing/hdmi_ddr_ov5640_top.rtr','reference/native/hdmi_ddr_ov5640_top.rtr'),
 (RUN/'place_route/hdmi_ddr_ov5640_top.prr','reference/native/hdmi_ddr_ov5640_top.prr'),
 (AUDIT/'evidence/review_evidence/AB_critical_paths.json','reference/AB_critical_paths.json'),
 (AUDIT/'evidence/review_evidence/A03_shared_comparison_recheck.json','reference/A03_shared_comparison_recheck.json'),
 (AUDIT/'reports/A01_AB单seed物理诊断与四层资源账本.md','reference/A01_既有报告.md'),
 (AUDIT/'reports/A03_共享仿真与资源复核.md','reference/A03_既有报告.md')]: copy_verified(p,rel)
rtl=(RUN/'source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8').splitlines()
anchors=[{'line':i,'text':s} for i,s in enumerate(rtl,1) if any(k in s for k in ['last_use','Q_SELECT:','Q_CHECK:','Q_ELIG:','Q_ALLOC:','Q_DONE:','older=','i_frame_clear)'])]
dump('evidence/source_anchors.json',anchors)
rtr=(RUN/'report_timing/hdmi_ddr_ov5640_top.rtr').read_text(encoding='utf-8')
start=rtr.index('Startpoint  : u_correction/u_core/u_cache/qid[3][5]')
end=rtr.index('Slack (VIOLATED)',start)
end=rtr.index('\n',end)
excerpt=rtr[start:end]
(ROOT/'evidence/critical_path_native_excerpt.txt').write_text(excerpt,encoding='utf-8')
paths=json.loads((AUDIT/'evidence/review_evidence/AB_critical_paths.json').read_text(encoding='utf-8'))
negative=[r for r in paths if float(r['Slack'])<0]
performance=json.loads((AUDIT/'evidence/review_evidence/A03_shared_comparison_recheck.json').read_text(encoding='utf-8'))
stress=next(r for r in performance['checks'] if r['candidate']=='AB' and r['profile']=='real_stress')
facts={'scope':'existing baseline evidence plus arithmetic; no candidate implementation',
 'baseline_core_sha256':sha(RUN/'source/rtl/undistort_core.v'),
 'baseline_cache_sha256':sha(RUN/'source/rtl/undistort_cache_ab.v'),
 'baseline_map_sha256':sha(RUN/'source/rtl/undistort_map.v'),
 'negative_paths_in_existing_selected_path_json':negative,
 'coverage_warning':'selected paths only; not all 4630 failing endpoints',
 'critical_route_segments_ns':[1.430,3.122,0.617,1.369,2.543],
 'route_sum_ns':sum([1.430,3.122,0.617,1.369,2.543]),
 'largest_two_routes_ns':3.122+2.543,
 'largest_two_fraction_of_route':(3.122+2.543)/9.081,
 'data_delay_ns':10.016,'logic_delay_ns':0.935,'route_delay_ns':9.081,
 'data_delay_budget_if_other_terms_unchanged_ns':10.016-2.585,
 'required_route_reduction_if_other_terms_unchanged_ns':2.585,
 'required_route_reduction_fraction':2.585/9.081,
 'native_last_use_DFF_count':4032,'declared_last_use_bits':192*22,
 'proposed_done_mask_logical_bits':192,
 'four_independent_masks_logical_bits':4*192,
 'incremental_mask_bits_fraction_of_baseline_cache_FF':192/8084,
 'shared_AB_stress':stress,
 '30fps_cycle_budget':125000000/30,
 'stress_remaining_cycles_to_30fps_assuming_125MHz':125000000/30-stress['cycles'],
 'predicted_new_WNS':None,'predicted_new_LUT_FF_DRM':None,'RTL_verified':False,'physical_verified':False}
dump('evidence/design_facts.json',facts)
# Abstract per-entry write-priority truth table. Symbolic values are NOT RTL simulation.
cases=0
for reset,clear,touch,tmatch,amatch,dmatch in itertools.product([False,True],repeat=6):
 for state in ['OTHER','ALLOC','DONE']:
  old='OLD'
  if not reset and not clear:
   if touch and tmatch:old='TOUCH_SEQ'
   if state=='ALLOC' and amatch:old='QSEQ'
   if state=='DONE' and dmatch:old='QSEQ'
  new='OLD'
  if not reset and not clear:
   qwrite=(state=='ALLOC' and amatch) or (state=='DONE' and dmatch)
   if qwrite:new='QSEQ'
   elif touch and tmatch:new='TOUCH_SEQ'
  if old!=new:raise ValueError('priority algebra mismatch')
  cases+=1
# Every equality pattern of four IDs is represented by four abstract labels.
patterns=0
for ids in itertools.product(range(4),repeat=4):
 mask=set()
 for k,slot in enumerate(ids):
  mask.add(slot)
  if mask!=set(ids[:k+1]):raise ValueError('prefix invariant mismatch')
 if mask!=set(ids):raise ValueError('done mask mismatch')
 patterns+=1
checks={'scope':'DESIGN_ALGEBRA_ONLY; no candidate RTL, functional simulation, formal RTL proof or PDS execution',
 'per_entry_write_priority_combinations':cases,'per_entry_write_priority':'PASS_ABSTRACT',
 'four_ID_equality_patterns':patterns,'resolved_prefix_mask_union':'PASS_ABSTRACT',
 'assumptions':['legal state transitions resolve one key in successful Q_CHECK or Q_ALLOC',
 'successful resolved IDs remain protected by original qfound/qid machinery',
 'mask is cleared before each lookup and on reset/frame_clear',
 'all successful resolution events must update mask with actual resolved sel/chosen, not old qid'],
 'not_proved':['RTL event implementation','physical locality','timing closure','hardware behavior','all legacy error inputs']}
dump('evidence/design_algebra_checks.json',checks)
test_inventory=[]
for rel in ['run_validation.py','run_validation_exact64.py','sim/cache72_ab_tb.v','sim/segment_cache_tb.v','sim/cache_mode_switch_tb.v','sim/cache_boundary_r3_tb.v','sim/calibration_core_ab_tb.v','sim/c6_host_arb_tb.v','sim/c6_real_subsystem_tb.v','sim/c6_display_bridge_tb.v','integration/tb/corr_top_tb.v']:
 p=TEST/rel
 test_inventory.append({'test_reference':rel,'existing_source':str(p),'exists':p.is_file(),'sha256':sha(p) if p.is_file() else None,'executed_in_this_plan':False})
dump('evidence/existing_test_entry_index.json',test_inventory)
dump('evidence/source_identity.json',sources)
print(json.dumps({'source_files_verified':len(sources),'write_priority_cases':cases,'mask_equality_patterns':patterns,'cache_sha256':facts['baseline_cache_sha256'],'native_negative_selected_paths':len(negative),'30fps_cycles_remaining':facts['stress_remaining_cycles_to_30fps_assuming_125MHz']},ensure_ascii=False,indent=2))

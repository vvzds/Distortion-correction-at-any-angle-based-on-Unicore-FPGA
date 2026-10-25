"""Run P4 only if final P3 evidence still shows its targeted mask violation."""
from pathlib import Path
import json,time,subprocess,sys
R=Path(__file__).resolve().parent
P3=R.parent/'AB_P3缓存实施_20261024'
limit=time.monotonic()+7200
print('WAITING_FOR_P3_FINAL_PHYSICAL_EVIDENCE',flush=True)
while not (P3/'results/focused_timing.json').exists():
    if time.monotonic()>limit:raise TimeoutError('P3 final physical evidence unavailable')
    time.sleep(3)
receipt=json.loads((P3/'results/physical_seed2/process_receipt.json').read_text(encoding='utf-8'))
assert receipt['state']=='FINISHED' and receipt['exit_code']==0 and not receipt['changed_input_files']
full=json.loads((P3/'results/physical_comparison.json').read_text(encoding='utf-8'))
focused=json.loads((P3/'results/focused_timing.json').read_text(encoding='utf-8'))
paths=list(full['candidate']['worst_reported_paths'])
for report in focused['focused_reports'].values():
    for group in report.get('path_groups',{}).values():paths+=group['worst_paths']
target=[x for x in paths if x['slack_ns']<0 and '/u_cache/done_mask' in x['end']]
if not target:
    print('HOLD_FOR_PATH_REVIEW: no final reported negative done_mask path; P4 PNR not launched',flush=True)
    raise SystemExit(0)
(R/'results/p4_physical_start_basis.json').write_text(json.dumps({'p3_cache_sha256':receipt['before']['source/rtl/undistort_cache_ab.v'],'target_paths':target,'reason':'P3 final report still has negative cache done_mask paths; P4 precomputes stable duplicate comparisons without adding cycles'},indent=2),encoding='utf-8')
def run(name,*args):subprocess.run([sys.executable,'-B','-X','utf8',str(R/name),*args],check=True)
run('run_physical.py','--provisional-overlap')
run('inspect_physical.py')
run('inspect_focused_timing.py')
run('compare_warnings.py')
print('P4_PHYSICAL_EVIDENCE_READY; regression and final review still required',flush=True)
p=R/'results/regression_p4/summary.json';limit=time.monotonic()+14400
while not p.exists():
    if time.monotonic()>limit:raise TimeoutError('No P4 regression summary')
    time.sleep(3)
data=json.loads(p.read_text(encoding='utf-8'))
assert len(data['results'])==6 and all(x['passed'] for x in data['results'])
run('compare_regression.py')
print('P4_EVIDENCE_READY',flush=True)

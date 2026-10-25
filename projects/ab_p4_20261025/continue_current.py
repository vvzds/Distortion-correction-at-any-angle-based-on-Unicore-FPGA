"""Continue P4 after controlled stop of the nonconverging P3 attempt."""
from pathlib import Path
import json,time,subprocess,sys
R=Path(__file__).resolve().parent;P3=R.parent/'AB_P3缓存实施_20261024'
p3=json.loads((P3/'results/physical_seed2/process_receipt.json').read_text(encoding='utf-8'))
assert p3['state']=='FINISHED' and p3['exit_code']!=0 and not p3['changed_input_files']
assert (P3/'results/physical_seed2/controlled_stop.json').exists()
p1=json.loads((R/'prior_p1/physical_comparison.json').read_text(encoding='utf-8'))['candidate']
targets=[x for x in p1['worst_reported_paths'] if x['slack_ns']<0 and '/u_cache/done_mask' in x['end']]
assert targets
(R/'results/p4_physical_start_basis.json').write_text(json.dumps({'reason':'P1 native done_mask violation motivates stable-key precomputation; P3 physical attempt was stopped after routing stagnation, with no final timing verdict. P4 focused equivalence and seven mutation checks passed.', 'target_paths_from_p1':targets,'p3_exit_code':p3['exit_code']},indent=2),encoding='utf-8')
def run(name,*args):subprocess.run([sys.executable,'-B','-X','utf8',str(R/name),*args],check=True)
run('run_physical.py','--provisional-overlap')
run('inspect_physical.py')
run('inspect_focused_timing.py')
run('compare_warnings.py')
print('P4_PHYSICAL_EVIDENCE_READY; waiting full regression gate',flush=True)
p=R/'results/regression_p4/summary.json';limit=time.monotonic()+14400
while not p.exists():
    if time.monotonic()>limit:raise TimeoutError('P4 regression summary absent')
    time.sleep(3)
d=json.loads(p.read_text(encoding='utf-8'))
assert len(d['results'])==6 and all(x['passed'] for x in d['results'])
run('compare_regression.py')
print('P4_EVIDENCE_READY',flush=True)

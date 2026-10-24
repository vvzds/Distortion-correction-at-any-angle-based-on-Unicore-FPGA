"""Overlap offline PNR with slow behavioural regression; no early acceptance."""
from pathlib import Path
import json,subprocess,sys,time
R=Path(__file__).resolve().parent
def run(name,*args):
    subprocess.run([sys.executable,'-B','-X','utf8',str(R/name),*args],check=True)
run('run_physical.py','--provisional-overlap')
run('inspect_physical.py')
run('inspect_focused_timing.py')
run('compare_warnings.py')
print('PHYSICAL_EVIDENCE_READY; waiting for full regression acceptance gate',flush=True)
limit=time.monotonic()+7200
p=R/'results/regression_p3/summary.json'
while not p.exists():
    if time.monotonic()>limit:raise TimeoutError('No full regression summary')
    time.sleep(3)
d=json.loads(p.read_text(encoding='utf-8'))
assert len(d['results'])==6 and all(x['passed'] for x in d['results'])
run('compare_regression.py')
print('P3_EVIDENCE_READY; final review required',flush=True)

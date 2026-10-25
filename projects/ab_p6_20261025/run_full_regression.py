"""Run all six frozen full cases only after this revision passes early gates."""
from pathlib import Path
import subprocess,sys,json,datetime,hashlib
R=Path(__file__).resolve().parent;O=R/'results';record=O/'regression_coordinator.json'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
assert load(O/'synthesis_gate/result.json')['passed']
assert len(load(O/'equivalence_p6/summary.json')['results'])==5
assert all(x['pass'] for x in load(O/'equivalence_p6/summary.json')['results'])
negative=load(O/'negative_checks_p6/summary.json')
assert len(negative)==11 and all(x['detected'] for x in negative)
assert not record.exists()
cmd=[sys.executable,'-B','-X','utf8',str(R/'candidate/run_validation.py'),
     '--cases','integration','legacy_sim','identity','real_joint','c6_real_subsystem','c6_host_arb',
     '--out',str(O/'regression_p6'),'--tool-root',
     r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app',
     '--jobs','3','--timeout','14400']
data=dict(state='RUNNING',argv=cmd,cache_sha256=hashlib.sha256((R/'candidate/source/rtl/undistort_cache_ab.v').read_bytes()).hexdigest(),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
def save():record.write_text(json.dumps(data,indent=2),encoding='utf-8')
with (O/'regression_console.log').open('wb') as f:
    p=subprocess.Popen(cmd,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    data['pid']=p.pid;save();print('REGRESSION_RUNNING',p.pid,flush=True)
    rc=p.wait()
data.update(state='FINISHED',exit_code=rc,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());save()
if rc==0:
    rc=subprocess.run([sys.executable,'-B','-X','utf8',str(R/'compare_regression.py')],stdout=subprocess.DEVNULL).returncode
    data['comparison_exit_code']=rc;save()
print(json.dumps(data,indent=2));raise SystemExit(rc)

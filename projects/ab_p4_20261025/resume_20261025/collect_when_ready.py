"""Collect current results once runners finish; never launch another candidate."""
from pathlib import Path
import time,subprocess,sys,json,datetime
N=Path(__file__).resolve().parent;R=N.parent
todo={'physical':R/'results/physical_seed2_resume_20261025/process_receipt.json',
      'regression':R/'results/regression_p4_resume_20261025/summary.json'}
limit=time.monotonic()+15000
errors=[]
def run(script):
    with (N/(Path(script).stem+'_console.log')).open('wb') as log:
        p=subprocess.run([sys.executable,'-B','-X','utf8',str(N/script)],stdout=log,stderr=subprocess.STDOUT)
    print('POSTPROCESS',script,p.returncode,flush=True)
    if p.returncode:errors.append({'script':script,'exit_code':p.returncode})
while todo:
    for kind,path in list(todo.items()):
        if not path.exists():continue
        data=json.loads(path.read_text(encoding='utf-8'))
        if kind=='physical':
            if data['state'] in ('STARTING','RUNNING'):continue
            if data.get('exit_code')==0 and not data['changed_input_files']:
                run('inspect_physical.py');run('inspect_focused_timing.py');run('compare_warnings.py')
            else:errors.append({'physical_exit_code':data.get('exit_code'),'state':data['state']})
        else:
            if len(data['results'])==2 and all(x['passed'] for x in data['results']):run('compare_regression.py')
            else:errors.append({'regression':data})
        del todo[kind]
    if time.monotonic()>limit:raise TimeoutError('Current runner collection limit exceeded')
    if todo:time.sleep(3)
out={'state':'COLLECTED' if not errors else 'REVIEW_REQUIRED','errors':errors,'saved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(N/'collection_summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)

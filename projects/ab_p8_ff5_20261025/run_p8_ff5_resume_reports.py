"""Wait for the already-started single PNR; never starts another build."""
from pathlib import Path
import subprocess,sys,time,json,datetime,shutil
R=Path(r'C:\Users\lenovo\Desktop\ww\AB_P8_FF5物理验证_20261025');O=R/'results'
assert not (O/'post_resume_coordinator.json').exists()
record=dict(state='WAITING_FOR_EXISTING_PNR',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),steps=[])
def save():(O/'post_resume_coordinator.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
save();start=time.monotonic()
while True:
    run=json.loads((O/'physical_resume/process_receipt.json').read_text(encoding='utf-8'))
    if run['state'] not in ('STARTING','RUNNING'):break
    if time.monotonic()-start>7500:raise RuntimeError('Existing physical run wait limit reached; inspect run, do not restart it')
    time.sleep(10)
if run['state']!='FINISHED' or run['exit_code']!=0:
    record.update(state='NO_COMPLETE_PHYSICAL_DATABASE',physical_state=run['state'],physical_exit_code=run['exit_code']);save();raise SystemExit(2)
shutil.copy2(Path(__file__).parent/'compare_p8_ff5.py',R/'compare_p8_ff5.py')
record['state']='REPORTING';save()
for script in ('inspect_physical.py','run_focused_reports.py','run_focused_diagnostic.py','compare_p8_ff5.py'):
    cmd=[sys.executable,'-X','utf8',str(R/script)]
    with (O/(script.removesuffix('.py')+'_console.log')).open('wb') as log:
        p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        record['active_step']=dict(script=script,pid=p.pid);save()
        rc=p.wait(timeout=1500)
    record['steps'].append(dict(script=script,argv=cmd,exit_code=rc));save()
    print(script,'exit',rc,flush=True)
    if rc:record['state']='REPORT_ERROR';save();raise SystemExit(rc)
record.update(state='FINISHED',finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());record.pop('active_step',None);save()
print('POST_PHYSICAL_REPORTS_FINISHED',flush=True)

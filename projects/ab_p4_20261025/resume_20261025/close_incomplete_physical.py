"""Verify terminal run, close only its verified residual PDS descendants, preserve receipts."""
from pathlib import Path
import importlib.util, json, hashlib, datetime, subprocess
N=Path(__file__).resolve().parent; R=N.parent
O=R/'results/physical_seed2_resume_20261025'; p=O/'process_receipt.json'
run=json.loads(p.read_text(encoding='utf-8'))
complete_artifacts=(R/'physical/host_seed2_resume_20261025/report_timing/hdmi_ddr_ov5640_top.rtr').is_file() and 'P4_UNRESTRICTED_REPORT_RESTORED' in (O/'console.log').read_text(errors='replace')
assert run['state'] in ('FINISHED','TIMEOUT') and (run['exit_code']!=0 or not complete_artifacts), 'Never stop a running or completed candidate'
spec=importlib.util.spec_from_file_location('snapshot_tool',R/'process_snapshot.py')
s=importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
root=int(run['pid']); assert root==32400,'Review PID identity if runner differs'
before=s.snapshot(); selected={root}; changed=True
while changed:
    changed=False
    for row in before:
        if row['ppid'] in selected and row['pid'] not in selected:
            selected.add(row['pid']); changed=True
targets=[row for row in before if row['pid'] in selected]
assert all(row['name'].lower()=='pds_shell.exe' for row in targets), targets
rootrow=next((row for row in targets if row['pid']==root),None)
if rootrow: assert rootrow['ppid']==8488,'Unexpected root parent; do not kill unrelated work'
old_receipt=p.read_bytes()
backup=O/'process_receipt_before_post_run_cleanup.json'
assert not backup.exists(),'Do not overwrite earlier cleanup evidence'
backup.write_bytes(old_receipt)
log={'method':'Stop only terminal-run PDS tree verified through Windows Toolhelp snapshot','root_pid':root,'before':targets,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
if targets:
    ids=','.join(str(x['pid']) for x in reversed(targets))
    command=['powershell.exe','-NoProfile','-NonInteractive','-Command',f'Stop-Process -Id {ids} -Force -ErrorAction Stop']
    result=subprocess.run(command,capture_output=True)
    log.update(command=command,returncode=result.returncode,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace'))
after=s.snapshot(); remain=[x for x in after if x['pid'] in selected and x['name'].lower()=='pds_shell.exe']
log.update(after=remain,all_task_processes_stopped=not remain,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(O/'final_process_check.json').write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
assert not remain,'Task processes still running: archive forbidden'
current=hashlib.sha256((O/'console.log').read_bytes()).hexdigest()
if current!=run['console_sha256']:
    run['console_sha256_before_post_run_cleanup']=run['console_sha256']
    run['console_sha256']=current
    run['post_run_cleanup']={'evidence':'final_process_check.json','original_receipt':backup.name,'reason':'Original wrapper hashed console while a residual child still held stdout; final hash taken only after verified shutdown.','finished_utc':log['finished_utc']}
    p.write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'all_task_processes_stopped':not remain,'residual_pds_closed':len(targets),'final_console_sha256':current,'original_receipt_preserved':backup.name},ensure_ascii=False,indent=2))

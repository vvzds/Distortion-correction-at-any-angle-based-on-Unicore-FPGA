"""One fixed seed2 physical run; overlap is provisional until full regression passes."""
from pathlib import Path
import subprocess,os,json,hashlib,time,datetime,re,shutil
from process_snapshot import snapshot
R=Path(__file__).resolve().parent;P=R/'physical/host_seed2';O=R/'results/physical_seed2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
assert all(x['pass'] for x in json.loads((R/'results/equivalence_p7/summary.json').read_text())['results'])
assert all(x['detected'] for x in json.loads((R/'results/negative_checks_p7/summary.json').read_text()))
assert json.loads((R/'results/synthesis_gate/result.json').read_text())['passed'], 'Resource gate failed'
assert len(json.loads((R/'results/negative_checks_p7/summary.json').read_text()))==22
assert all(x['pass'] for x in json.loads((R/'results/banks_p7/summary.json').read_text())['results'])
expected='a9b516a3736adf5ad7f84198e7ef9b50023e62cca95e2208c63f6d811a6eaf53'
assert sha(P/'source/rtl/undistort_cache_ab.v')==sha(R/'candidate/source/rtl/undistort_cache_ab.v')==expected
driver=(P/'analysis.tcl').read_text();assert 'gen_bit_stream' not in driver and 'file rename' not in driver and 'file copy' not in driver
assert driver.count('report_timing ')==1 and 'pnr -gplace_seed 2 -groute_seed 2' in driver
# Preserve the early native artifacts before this complete flow regenerates them.
gate_native=R/'results/synthesis_gate/native'
gate_native.mkdir(exist_ok=False)
for name in ('synthesize/hdmi_ddr_ov5640_top.snr','synthesize/hdmi_ddr_ov5640_top_syn.vm','device_map/hdmi_ddr_ov5640_top.dmr'):
    a=P/name;b=gate_native/name;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
gate_files={p.relative_to(gate_native).as_posix():sha(p) for p in gate_native.rglob('*') if p.is_file()}
(R/'results/synthesis_gate/native_identity.json').write_text(json.dumps(gate_files,indent=2),encoding='utf-8')
O.mkdir(parents=True,exist_ok=False)
tool=Path(r'D:\FPGA PDS\PDS_2022.2-SP6.1-win64\bin\pds_shell.exe')
assert sha(tool)=='f22f86527d72ce7980dadad3adb189ee1d0271979d053e15d97da954b6848d0f'
drive=next(c+':' for c in 'QRSTUVWXY' if not Path(c+':/').exists())
env=dict(os.environ);env['PATH']=str(tool.parent)+os.pathsep+env.get('PATH','')
inputs=json.loads((R/'physical/input_identity.json').read_text(encoding='utf-8'))['inputs']
before={x['file']:sha(P/x['file']) for x in inputs}
assert all(before[x['file']]==x['sha256'] for x in inputs)
record=dict(state='STARTING',started_utc=now(),tool=str(tool),tool_sha256=sha(tool),before=before,
    provisional_overlap=True,acceptance_requires_full_regression_comparison=True,
    scope='Same 125MHz seed2 offline candidate; original FDC/IP; no bitstream or board claim',
    stop_policy=dict(max_wall_seconds=7200,plateau_min_iteration=80,window_iterations=20,
                     minimum_unrouted=1000,required_best_improvement_fraction=0.05))
def save():(O/'process_receipt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
def stop_tree(proc):
    rows=snapshot();owned={proc.pid}
    while True:
        expanded=owned|{x['pid'] for x in rows if x['ppid'] in owned}
        if expanded==owned:break
        owned=expanded
    targets=[x for x in rows if x['pid'] in owned]
    record['stopped_processes']=targets;save()
    # Kill only the explicitly enumerated descendants of this run.
    for target in reversed(targets):
        subprocess.run(['powershell.exe','-NoProfile','-Command',f"Stop-Process -Id {target['pid']} -Force -ErrorAction SilentlyContinue"],capture_output=True)
    try:proc.wait(timeout=15)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=15)
    record['owned_processes_remaining']=[x for x in snapshot() if x['pid'] in owned]
subprocess.run(['subst',drive,str(P)],check=True)
try:
    cmd=[str(tool),'-file',drive+'/analysis.tcl','-work_dir',drive+'/','-project_name','ab_seed2_analysis']
    record.update(argv=cmd,mapping=dict(drive=drive,target=str(P)));save();tick=time.monotonic()
    with (O/'console.log').open('wb') as log:
        proc=subprocess.Popen(cmd,cwd=P,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        record.update(state='RUNNING',pid=proc.pid);save();print('PDS_RUNNING',proc.pid,flush=True)
        reason=None
        while proc.poll() is None:
            body=(O/'console.log').read_text(errors='replace')
            routes=[(int(i),int(n)) for n,i in re.findall(r'Unrouted nets (\d+) at the end of iteration (\d+)',body)]
            record.update(elapsed_s=round(time.monotonic()-tick,1),last_route=routes[-1] if routes else None)
            if len(routes)>=40 and routes[-1][0]>=80:
                previous=min(n for _,n in routes[-40:-20]);latest=min(n for _,n in routes[-20:])
                if latest>=1000 and latest>=previous*0.95:
                    reason='CONTROLLED_STOP_ROUTE_PLATEAU'
                    record['plateau_evidence']=dict(previous_window=routes[-40:-20],latest_window=routes[-20:],previous_best=previous,latest_best=latest)
            if (O/'cancel_requested.json').exists():reason='CONTROLLED_STOP_REQUESTED'
            if time.monotonic()-tick>=7200:reason='CONTROLLED_STOP_WALL_LIMIT'
            save()
            if reason:stop_tree(proc);break
            time.sleep(10)
        rc=proc.wait()
    record.update(state=reason or 'FINISHED',exit_code=rc,finished_utc=now())
finally:
    subprocess.run(['subst',drive,'/D'],check=True)
    record['changed_input_files']=[f for f,h in before.items() if not (P/f).is_file() or sha(P/f)!=h]
    record['console_sha256']=sha(O/'console.log')
    record['bitstreams_present']=[str(p.relative_to(P)) for p in P.rglob('*.sbit')]
    save()
print(json.dumps({k:v for k,v in record.items() if k!='before'},indent=2))
raise SystemExit(0 if record['state']=='FINISHED' and rc==0 else 2)

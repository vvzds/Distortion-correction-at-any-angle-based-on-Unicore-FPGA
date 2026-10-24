"""Single seed2 diagnostic after explicit functional gates; never creates a bitstream."""
from pathlib import Path
import subprocess,os,json,hashlib,time,datetime,sys
R=Path(__file__).resolve().parent
P=R/'physical/host_seed2'
O=R/'results/physical_seed2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
provisional='--provisional-overlap' in sys.argv
gates=[('results/equivalence_p3/summary.json','pass')]
if not provisional:gates.append(('results/regression_p3/summary.json','passed'))
for rel,key in gates:
    d=json.loads((R/rel).read_text())
    assert all(x[key] for x in d['results']),rel
assert all(x['detected'] for x in json.loads((R/'results/negative_checks_p3/summary.json').read_text()))
if not provisional:assert json.loads((R/'results/regression_comparison.json').read_text(encoding='utf-8'))['passed']
expected='614797ccd5a2f122caed1050fc013e28e3852f14923b3a037fa7c5d453a65330'
assert sha(P/'source/rtl/undistort_cache_ab.v')==expected
assert sha(R/'candidate/source/rtl/undistort_cache_ab.v')==expected
assert 'gen_bit_stream' not in (P/'analysis.tcl').read_text()
O.mkdir(parents=True,exist_ok=False)
tool=Path(r'D:\FPGA PDS\PDS_2022.2-SP6.1-win64\bin\pds_shell.exe')
assert sha(tool)=='f22f86527d72ce7980dadad3adb189ee1d0271979d053e15d97da954b6848d0f'
drive=next(c+':' for c in 'QRSTUVWXY' if not Path(c+':/').exists())
env=dict(os.environ);env['PATH']=str(tool.parent)+os.pathsep+env.get('PATH','')
input_rows=json.loads((R/'physical/input_identity.json').read_text(encoding='utf-8'))['inputs']
before={row['file']:sha(P/row['file']) for row in input_rows}
assert all(before[row['file']]==row['sha256'] for row in input_rows),'physical input drift'
record={'state':'STARTING','started_utc':now(),'tool':str(tool),'tool_sha256':sha(tool),'before':before,'scope':'same seed2 offline diagnosis; original UART/FDC limitations retained; no bitstream or board validation'}
record['provisional_overlap']=provisional
record['acceptance_requires_full_regression_comparison']=True
def save():(O/'process_receipt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
subprocess.run(['subst',drive,str(P)],check=True)
try:
    cmd=[str(tool),'-file',drive+'/analysis.tcl','-work_dir',drive+'/','-project_name','ab_seed2_analysis']
    record['argv']=cmd;record['mapping']={'drive':drive,'target':str(P)};save()
    with (O/'console.log').open('wb') as log:
        proc=subprocess.Popen(cmd,cwd=P,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        record.update(state='RUNNING',pid=proc.pid);save()
        print('PDS_RUNNING',proc.pid,flush=True)
        try:rc=proc.wait(timeout=7200)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
            rc=124
    record.update(state='FINISHED' if rc!=124 else 'TIMEOUT',exit_code=rc,finished_utc=now())
finally:
    subprocess.run(['subst',drive,'/D'],check=True)
    record['changed_input_files']=[name for name,h in before.items() if not (P/name).is_file() or sha(P/name)!=h]
    record['console_sha256']=sha(O/'console.log')
    record['bitstreams_present']=[str(p.relative_to(P)) for p in P.rglob('*.sbit')]
    save()
print(json.dumps({k:v for k,v in record.items() if k!='before'},indent=2))
raise SystemExit(0 if record.get('exit_code')==0 else 2)

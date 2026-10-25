from pathlib import Path
import subprocess,hashlib,json,time,datetime
from concurrent.futures import ThreadPoolExecutor
R=Path(__file__).resolve().parent
TOOL=Path(r'C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app')
out=R/'results/banks_p7';out.mkdir(parents=True,exist_ok=False)
drive=next(c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
subprocess.run(['subst',drive,str(TOOL)],check=True)
tool=Path(drive+'/')
cases=[('banks','cache_p7_banks_tb.sv','cache_p7_banks_tb','P7_BANKS_EQUIVALENCE PASS')]
def run(case):
    name,tb,top,marker=case
    d=out/name;d.mkdir()
    inputs=[R/'tests'/tb,R/'candidate/source/rtl/undistort_cache_ab.v',R/'baseline/undistort_cache_ab_reference.v']
    before={str(p.relative_to(R)):sha(p) for p in inputs}
    compile_cmd=[str(tool/'bin/iverilog.exe'),'-B',str(tool/'lib/ivl'),'-g2012','-s',top,'-o',str(d/'sim.vvp')]+[str(p) for p in inputs]
    commands=[compile_cmd,[str(tool/'bin/vvp.exe'),str(d/'sim.vvp')]]
    steps=[];start=time.time()
    for i,cmd in enumerate(commands):
        with (d/('compile.log' if i==0 else 'simulation.log')).open('wb') as log:
            try:rc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
            except subprocess.TimeoutExpired:rc=124
        steps.append({'argv':cmd,'exit_code':rc})
        if rc:break
    log=(d/'simulation.log').read_text(errors='replace') if (d/'simulation.log').exists() else ''
    good=len(steps)==2 and all(s['exit_code']==0 for s in steps) and marker in log
    after={str(p.relative_to(R)):sha(p) for p in inputs};assert after==before
    result={'case':name,'pass':good,'elapsed_s':time.time()-start,'steps':steps,'inputs_before':before,'inputs_after':after,'simulation_log_sha256':sha(d/'simulation.log') if (d/'simulation.log').exists() else None}
    (d/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(name,'PASS' if good else 'FAIL',log[-600:],flush=True)
    return result
try:
    with ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(run,cases))
finally:subprocess.run(['subst',drive,'/D'],check=True)
(out/'summary.json').write_text(json.dumps({'tool_sha256':sha(TOOL/'bin/iverilog.exe'),'results':results},indent=2),encoding='utf-8')
raise SystemExit(0 if all(x['pass'] for x in results) else 1)

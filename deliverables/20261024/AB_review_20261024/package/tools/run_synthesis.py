"""Isolated AB synthesis; serial runs, complete inputs/logs, no bitstream/PNR."""
from pathlib import Path
from datetime import datetime, timezone
import argparse,hashlib,json,re,subprocess,time,sys

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def inputs(folder):
    files=[p for sub in ('source','ipcore') if (folder/sub).exists() for p in (folder/sub).rglob('*') if p.is_file()]
    files += [p for p in folder.iterdir() if p.suffix in ('.tcl','.fdc','.pds') and p.name!='impl.tcl']
    files += [Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(files)}

def run(kind,exe,timeout):
    folder=ROOT/kind;out=ROOT/'evidence'/('synth_'+kind)
    out.mkdir(exist_ok=False)
    before=inputs(folder);tool_hash=sha(exe)
    drive=next((x+':' for x in 'QPRSTUVWXYZ' if not Path(x+':/').exists()),None)
    if drive is None:raise RuntimeError('no free subst drive')
    subprocess.run(['subst.exe',drive,str(folder)],check=True,capture_output=True)
    script='synth.tcl' if kind=='core' else 'synth_only.tcl'
    command=[str(exe),'-file',drive+'/'+script,'-work_dir',drive+'/','-project_name','ab_r1r4_'+kind]
    record=dict(scope='SYNTHESIS_ONLY_SP6.1_NOT_SP6.4_PNR',kind=kind,command=command,cwd=str(folder),
                start_utc=now(),timeout_seconds=timeout,tool_sha256_before=tool_hash,inputs_before=before,
                subst=dict(drive=drive,target=str(folder)),status='RUNNING')
    dump(out/'process_receipt.json',record)
    tick=time.monotonic();code=None
    try:
        with (out/'console.log').open('wb') as stream:
            proc=subprocess.Popen(command,cwd=folder,stdout=stream,stderr=subprocess.STDOUT)
            record['pid']=proc.pid;dump(out/'process_receipt.json',record)
            try:code=proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                killed=subprocess.run(['taskkill.exe','/PID',str(proc.pid),'/T','/F'],capture_output=True)
                (out/'timeout_cleanup.log').write_bytes(killed.stdout+killed.stderr)
                proc.wait(timeout=30);code=124
    finally:
        subprocess.run(['subst.exe',drive,'/D'],check=True,capture_output=True)
        after=inputs(folder)
        record.update(end_utc=now(),elapsed_seconds=time.monotonic()-tick,exit_code=code,
                      inputs_after=after,inputs_unchanged=before==after,tool_sha256_after=sha(exe))
        log=(out/'console.log').read_text(encoding='utf-8',errors='replace')
        ok=code==0 and 'Process "Synthesize" done.' in log and not re.search(r'(?m)^E:',log)
        ok=ok and before==after and sha(exe)==tool_hash
        record.update(status='SYNTHESIS_COMPLETE' if ok else 'FAILED',console_sha256=sha(out/'console.log'),
                      pnr='NOT_RUN',bitstream='NOT_GENERATED',board='PAUSED',uart_loc_confirmed=False)
        artifacts=[p for sub in ('compile','synthesize') if (folder/sub).exists() for p in (folder/sub).rglob('*') if p.is_file()]
        record['artifacts']=[dict(file=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(artifacts)]
        reports=list((folder/'synthesize').glob('*.snr'))
        record['timing_rows']=[]
        for report in reports:
            text=report.read_text(encoding='utf-8',errors='replace')
            record['timing_rows'] += [line for line in text.splitlines() if 'MHz' in line and re.search(r'-?\d+\.\d+',line)]
        dump(out/'process_receipt.json',record)
    print(json.dumps(dict(kind=kind,status=record['status'],exit_code=code,seconds=record['elapsed_seconds'],timing_rows=record['timing_rows']),ensure_ascii=False),flush=True)
    return ok

def main():
    p=argparse.ArgumentParser();p.add_argument('--pds',type=Path,required=True);p.add_argument('--timeout',type=int,default=1800)
    p.add_argument('--cases',nargs='+',choices=['core','host'],default=['core','host']);a=p.parse_args()
    if not a.pds.is_file() or a.timeout<=0:p.error('existing PDS and positive timeout required')
    passed=[]
    for kind in a.cases:passed.append(run(kind,a.pds.resolve(),a.timeout))
    return 0 if all(passed) else 1
if __name__=='__main__':sys.exit(main())

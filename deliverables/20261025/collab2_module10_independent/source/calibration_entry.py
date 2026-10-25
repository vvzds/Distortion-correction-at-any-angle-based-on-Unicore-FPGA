"""Explicit, hash-checked binding to the repository calibration entry point."""
from pathlib import Path
import argparse,datetime,hashlib,json,subprocess,sys
EXPECTED={'calibrate.py':'e7581eedb1b62090eef15d0d083eb58b41f21b1965438613c45acc2fa7862ebe',
    'run_calibration.py':'edcb1c32ed3d0eeb09607872f17211d977ea7c969a4fe6e7ac6515644a8b58fd'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify_binding(root,expected=None):
    root=Path(root).resolve();records=[]
    for name,h in (expected or EXPECTED).items():
        p=root/'calibration'/name
        if not p.is_file() or sha(p)!=h:raise ValueError('Calibration source hash mismatch: '+str(p))
        records.append(dict(path=str(p),sha256=h))
    run=root/'calibration/run_calibration.py'
    if not run.is_file():raise ValueError('Checked calibration runner absent')
    return records

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',required=True,type=Path)
    ap.add_argument('--receipt',required=True,type=Path)
    ap.add_argument('--execute',action='store_true',help='Actually run the checked entry, otherwise inventory only')
    ap.add_argument('runner_args',nargs=argparse.REMAINDER)
    a=ap.parse_args()
    if a.receipt.exists():raise ValueError('Refuse to replace an earlier invocation record')
    records=verify_binding(a.repo)
    args=a.runner_args
    if args and args[0]=='--':args=args[1:]
    command=[sys.executable,'-B',str(a.repo.resolve()/'calibration/run_calibration.py'),*args]
    r=dict(time=datetime.datetime.now().astimezone().isoformat(),binding=records,argv=command,
        executed=False,mode='CHECK_ONLY',rollback='Original paths/copies preserved; historical results are not changed')
    if a.execute:
        p=subprocess.run(command);r.update(executed=True,mode='EXECUTED',exit_code=p.returncode)
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(mode=r['mode'],exit=r.get('exit_code')),ensure_ascii=False))
    return r.get('exit_code',0)

if __name__=='__main__':raise SystemExit(main())

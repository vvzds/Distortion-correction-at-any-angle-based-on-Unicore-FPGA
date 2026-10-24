"""Native isolated synthesis; preserves failures and never programs hardware."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pds',default='D:/FPGA PDS/site/PDS_2022.2-SP6.1-win64/bin/pds_shell.exe')
    ap.add_argument('--scratch',default='D:/FPGA PDS/sty/undistort_core_g1_verify/adaptive_gamma_20261024')
    a=ap.parse_args()
    name=datetime.datetime.now().strftime('synth_%Y%m%d_%H%M%S')
    work=Path(a.scratch)/name;work.mkdir(parents=True)
    out=ROOT/'evidence'/name;out.mkdir()
    shutil.copytree(ROOT/'rtl',work/'rtl');shutil.copy2(ROOT/'build/synthesize.tcl',work/'synthesize.tcl')
    cmd=[a.pds,'-file',str(work/'synthesize.tcl'),'-work_dir',str(work),'-project_name','adaptive_gamma']
    record=dict(command=cmd,started=datetime.datetime.now().astimezone().isoformat(),
                input_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (work/'rtl').glob('*.v')},
                scope='standalone synthesis only; not PNR or board timing closure',board_programmed=False)
    begin=time.monotonic()
    with (out/'console.log').open('wb') as log:
        p=subprocess.Popen(cmd,cwd=work,stdout=log,stderr=subprocess.STDOUT,
                           env=dict(os.environ,TEMP=str(work),TMP=str(work)))
        record['pid']=p.pid
        (out/'receipt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        try:code=p.wait(timeout=300)
        except subprocess.TimeoutExpired:p.kill();code=p.wait();record['timeout']=True
    text=(out/'console.log').read_text(encoding='utf-8',errors='replace')
    record.update(exit=code,seconds=time.monotonic()-begin,
                  status='PASS' if code==0 and 'ADAPTIVE_GAMMA_SYNTHESIS_COMPLETE' in text and '\nE:' not in text else 'FAILED')
    for folder in ('compile','synthesize'):
        if (work/folder).exists():shutil.copytree(work/folder,out/folder)
    for p in work.glob('*.pds'):shutil.copy2(p,out/p.name)
    (out/'receipt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2),flush=True)
    return 0 if record['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())

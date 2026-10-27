from advanced3_prepare_20261027 import *
import os,time

def main():
    pds=Path(r'D:/FPGA PDS/PDS_2022.2-SP6.1-win64/bin/pds_shell.exe')
    out=R/'verification/pds_compile'
    out.mkdir(exist_ok=False)
    text=(P/'run_host.tcl').read_text(encoding='utf-8').split('synthesize -ads')[0]
    (P/'compile_only.tcl').write_text(text+'\nputs "ADVANCED3_FULL_HOST_COMPILE_PASS"\nexit\n',encoding='utf-8')
    drive=next(c+':' for c in 'QRSTUVWX' if not Path(c+':/').exists())
    subprocess.run(['subst',drive,str(P)],check=True)
    before={p.relative_to(P).as_posix():sha(p) for d in ('source','ipcore') for p in (P/d).rglob('*') if p.is_file()}
    t=time.monotonic()
    try:
        cmd=[str(pds),'-file',drive+'/compile_only.tcl','-work_dir',drive+'/','-project_name','advanced3_gamma']
        with (out/'console.log').open('wb') as log:
            q=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=P,
                             env=dict(os.environ,PATH=str(pds.parent)+os.pathsep+os.environ.get('PATH','')),timeout=300)
        body=(out/'console.log').read_text(errors='replace')
        good=q.returncode==0 and 'ADVANCED3_FULL_HOST_COMPILE_PASS' in body
        receipt=dict(status='PASS' if good else 'FAIL',exit=q.returncode,seconds=round(time.monotonic()-t,3),
                     tool=str(pds),tool_sha256=sha(pds),argv=cmd,inputs=before,
                     changed_inputs=[p for p,h in before.items() if sha(P/p)!=h],
                     scope='PDS full board top compile/elaboration only; no synthesis/PNR/bitstream',
                     log_sha256=sha(out/'console.log'))
        assert not receipt['changed_inputs']
        (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print('FULL BOARD HOST COMPILE',receipt['status'],receipt['seconds'],flush=True)
        if not good:print(body[-4000:]);raise RuntimeError('PDS compile failed')
        for file in (P/'compile').glob('*.cmr'):shutil.copy2(file,out/file.name)
        shutil.copy2(__file__,R/Path(__file__).name)
    finally:subprocess.run(['subst',drive,'/D'],check=True)

if __name__=='__main__':main()

from advanced3_prepare_20261027 import *
import re,time

def main():
    out=R/'verification/local_smoke'
    out.mkdir(exist_ok=False)
    src=P/'source/rtl/corr_subsys'
    files=[src/n for n in ('adaptive_gamma.v','adaptive_gamma_curve.v','corr_top.v','param_mgr.v','gamma_lut.v','rect_wr_if.v','undistort_core.v','undistort_map.v','undistort_cache_ab.v','undistort_bilinear.v')]
    files.append(W/'work/advanced3_c50_smoke_tb.v')
    app=W/'work/simulator/iverilog/app'
    drive=next(c+':' for c in 'YXWVUTS' if not Path(c+':/').exists())
    subprocess.run(['subst',drive,str(app)],check=True)
    try:
        target=out/'sim.vvp'
        c=subprocess.run([str(Path(drive+'/bin/iverilog.exe')),'-B',str(Path(drive+'/lib/ivl')),'-g2012','-s','advanced3_c50_smoke_tb','-o',str(target)]+[str(p) for p in files],capture_output=True)
        (out/'compile.log').write_bytes(c.stdout+c.stderr)
        assert c.returncode==0,(out/'compile.log').read_text(errors='replace')[-4000:]
        with (out/'simulation.log').open('wb') as log:
            s=subprocess.run([str(Path(drive+'/bin/vvp.exe')),str(target)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
        body=(out/'simulation.log').read_text(errors='replace')
        passed=s.returncode==0 and body.count('=== ALL TESTS PASSED (err=0) ===')==1 and not re.search(r'FAIL|FATAL',body)
        receipt=dict(status='PASS' if passed else 'FAIL',scope='128-pixel C50 host boundary smoke; no full-frame or physical timing claim',
                     inputs={p.as_posix():sha(p) for p in files},simulator_sha256=sha(app/'bin/iverilog.exe'),log_sha256=sha(out/'simulation.log'))
        (out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(body,flush=True)
        if not passed:raise RuntimeError('Smoke failed')
        shutil.copy2(files[-1],R/'simulation/advanced3_c50_smoke_tb.v')
        shutil.copy2(__file__,R/Path(__file__).name)
    finally:subprocess.run(['subst',drive,'/D'],check=True)

if __name__=='__main__':main()

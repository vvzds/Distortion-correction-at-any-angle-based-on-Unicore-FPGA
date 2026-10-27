from advanced3_prepare_20261027 import *
import os, re, time, datetime

def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    app=W/'work/simulator/iverilog/app'
    out=R/'verification/full_frame_v3'
    out.mkdir(exist_ok=False)
    sim=R/'simulation'
    tb=sim/'advanced3_c50_write_tb_v3.v'
    shutil.copy2(W/'work/advanced3_c50_write_tb.v',tb)
    src=P/'source/rtl/corr_subsys'
    sources=[src/n for n in ('adaptive_gamma.v','adaptive_gamma_curve.v','corr_top.v','param_mgr.v','gamma_lut.v','rect_wr_if.v','undistort_core.v','undistort_map.v','undistort_cache_ab.v','undistort_bilinear.v')]+[tb]
    before={p.relative_to(R).as_posix():sha(p) for p in sources}
    drive=next(c+':' for c in 'YXWVUTS' if not Path(c+':/').exists())
    subprocess.run(['subst',drive,str(app)],check=True)
    receipt=dict(status='STARTING',started=datetime.datetime.now().astimezone().isoformat(),
                 scope='Three complete 1920x1080 frames at injected core output through real C50 corr_top/param_mgr/adaptive_gamma/rect_wr_if; does not test actual core mapping, physical DDR, or HDMI',
                 inputs=before,simulator_sha256=sha(app/'bin/iverilog.exe'),runtime_sha256=sha(app/'bin/vvp.exe'),
                 simulator_timeout_seconds=4200,physical_timing='NOT_RUN',board_test='NOT_RUN')
    save(out/'receipt.json',receipt)
    try:
        target=out/'full.vvp'
        cmd=[str(Path(drive+'/bin/iverilog.exe')),'-B',str(Path(drive+'/lib/ivl')),'-g2012','-s','advanced3_c50_write_tb','-o',str(target)]+[str(p) for p in sources]
        c=subprocess.run(cmd,capture_output=True)
        (out/'compile.log').write_bytes(c.stdout+c.stderr)
        if c.returncode:
            receipt.update(status='COMPILE_FAIL',compile_exit=c.returncode,compile_log_sha256=sha(out/'compile.log'))
            save(out/'receipt.json',receipt)
            raise RuntimeError(c.stderr.decode(errors='replace')[-4000:])
        receipt['compile_log_sha256']=sha(out/'compile.log')
        receipt['status']='RUNNING';save(out/'receipt.json',receipt)
        start=time.monotonic()
        with (out/'simulation.log').open('wb') as log:
            p=subprocess.Popen([str(Path(drive+'/bin/vvp.exe')),str(target)],cwd=sim,stdout=log,stderr=subprocess.STDOUT)
            try:
                while p.poll() is None:
                    if time.monotonic()-start>=4200:
                        p.kill();p.wait();receipt['status']='TIMEOUT';break
                    receipt['seconds']=round(time.monotonic()-start,1)
                    receipt['log_bytes']=(out/'simulation.log').stat().st_size
                    save(out/'receipt.json',receipt)
                    time.sleep(5)
            finally:
                if p.poll() is None:p.kill();p.wait()
        body=(out/'simulation.log').read_text(errors='replace')
        receipt.update(exit=p.returncode,seconds=round(time.monotonic()-start,2),
                       log_sha256=sha(out/'simulation.log'),
                       frame_starts=len(re.findall(r'^FRAME_START ',body,re.M)),
                       frame_progress=len(re.findall(r'^FRAME_PROGRESS ',body,re.M)),
                       frame_commits=len(re.findall(r'^FRAME=\d+ COMMIT=',body,re.M)),
                       inputs_changed=[name for name,h in before.items() if sha(R/name)!=h])
        passed=receipt['status']!='TIMEOUT' and p.returncode==0 and body.count('=== ALL TESTS PASSED (err=0) ===')==1 and not re.search(r'FAIL|FATAL',body) and receipt['frame_commits']==3 and not receipt['inputs_changed']
        if receipt['status']!='TIMEOUT':receipt['status']='PASS' if passed else 'FAIL'
        save(out/'receipt.json',receipt)
        print(json.dumps({k:receipt[k] for k in ('status','exit','seconds','frame_starts','frame_progress','frame_commits','log_sha256')},ensure_ascii=False),flush=True)
        print(body[-3000:],flush=True)
        if not passed:raise RuntimeError('Full-frame regression did not pass')
        shutil.copy2(__file__,R/Path(__file__).name)
    finally:subprocess.run(['subst',drive,'/D'],check=True)

if __name__=='__main__':main()

from advanced3_timing_prepare_20261027 import *
import datetime, os, subprocess, time

PDS=Path(r'D:/FPGA PDS/PDS_2022.2-SP6.1-win64/bin/pds_shell.exe')

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    mode=sys.argv[1]
    assert mode in ('synthesis','physical')
    out=R/'verification'/('timing_'+mode+'_seed7')
    out.mkdir(exist_ok=False)
    identity=json.loads((R/'verification/timing_input_identity.json').read_text(encoding='utf-8'))
    before={name:sha(PROJECT/name) for name in identity['source_hashes']}
    assert before=={name:row['candidate'] for name,row in identity['source_hashes'].items()}
    assert sha(PROJECT/'HDMI_DDR3_OV5640_test.fdc')==identity['constraint_sha256']
    script=PROJECT/('run_'+mode+'.tcl')
    expected=identity[mode+'_script_sha256']
    assert sha(script)==expected
    drive=next(c+':' for c in 'QRSTUVWX' if not Path(c+':/').exists())
    subprocess.run(['subst',drive,str(PROJECT)],check=True)
    max_seconds=2400 if mode=='synthesis' else 7200
    marker='ADV3_PHASE=SYNTHESIS_DONE' if mode=='synthesis' else 'ADV3_PHASE=FINISHED'
    cmd=[str(PDS),'-file',drive+'/'+script.name,'-work_dir',drive+'/','-project_name','advanced3_'+mode]
    receipt=dict(status='STARTING',mode=mode,started=datetime.datetime.now().astimezone().isoformat(),
                 tool=str(PDS),tool_sha256=sha(PDS),device='PG2L100H -6 FBG676',seed=7,
                 command=cmd,project=str(PROJECT),source_sha256=before,constraint_sha256=identity['constraint_sha256'],
                 script_sha256=expected,max_seconds=max_seconds,baseline_report=identity['baseline_seed7_report'])
    save(out/'receipt.json',receipt)
    start=time.monotonic()
    try:
        with (out/'console.log').open('wb') as log:
            process=subprocess.Popen(cmd,cwd=PROJECT,env=dict(os.environ,PATH=str(PDS.parent)+os.pathsep+os.environ.get('PATH','')),
                                     stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            receipt.update(status='RUNNING',pid=process.pid)
            save(out/'receipt.json',receipt)
            print('PDS_RUNNING',mode,process.pid,flush=True)
            while process.poll() is None:
                elapsed=time.monotonic()-start
                receipt['seconds']=round(elapsed,1)
                receipt['console_bytes']=(out/'console.log').stat().st_size
                save(out/'receipt.json',receipt)
                if elapsed>=max_seconds:
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True)
                    receipt['status']='TIMEOUT'
                    break
                time.sleep(15)
            code=process.wait(timeout=60)
        log=(out/'console.log').read_text(encoding='utf-8',errors='replace')
        changed=[name for name,h in before.items() if sha(PROJECT/name)!=h]
        finished=code==0 and marker in log and not changed
        if receipt['status']!='TIMEOUT':receipt['status']='PASS' if finished else 'FAIL'
        receipt.update(exit=code,seconds=round(time.monotonic()-start,1),marker_found=marker in log,
                       changed_source=changed,console_sha256=sha(out/'console.log'))
        save(out/'receipt.json',receipt)
        print('PDS_FINISHED',mode,receipt['status'],receipt['seconds'],flush=True)
        print(log[-2500:],flush=True)
        if not finished:raise RuntimeError('PDS '+mode+' did not complete successfully')
        for name in ('hdmi_ddr_ov5640_top.prr','hdmi_ddr_ov5640_top.rtr',
                     'hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt'):
            for p in PROJECT.rglob(name):
                if p.is_file() and p.stat().st_size<15_000_000:
                    shutil.copy2(p,out/name)
                    break
        shutil.copy2(__file__,R/Path(__file__).name)
    finally:
        subprocess.run(['subst',drive,'/D'],check=True)

if __name__=='__main__':main()

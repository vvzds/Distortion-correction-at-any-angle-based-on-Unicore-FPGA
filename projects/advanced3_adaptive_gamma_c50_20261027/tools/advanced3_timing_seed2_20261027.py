from advanced3_timing_prepare_20261027 import *
import datetime, os, subprocess, time

PDS=Path(r'D:/FPGA PDS/PDS_2022.2-SP6.1-win64/bin/pds_shell.exe')
ALT=R/'physical_seed2'
OUT=R/'verification/timing_physical_seed2'

def save(value):
    (OUT/'receipt.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    assert not ALT.exists() and not OUT.exists()
    identity=json.loads((R/'verification/timing_input_identity.json').read_text(encoding='utf-8'))
    OUT.mkdir()
    for folder in ('source','ipcore'):
        shutil.copytree(PROJECT/folder,ALT/folder)
    shutil.copy2(PROJECT/'HDMI_DDR3_OV5640_test.fdc',ALT/'HDMI_DDR3_OV5640_test.fdc')
    assert sha(ALT/'HDMI_DDR3_OV5640_test.fdc')==identity['constraint_sha256']
    before={name:sha(ALT/name) for name in identity['source_hashes']}
    assert before=={name:row['candidate'] for name,row in identity['source_hashes'].items()}
    old=(PROJECT/'run_physical.tcl').read_text(encoding='utf-8')
    assert old.count('pnr -gplace_seed 7 -groute_seed 7')==1
    (ALT/'run_physical.tcl').write_text(old.replace('pnr -gplace_seed 7 -groute_seed 7',
                                                    'pnr -gplace_seed 2 -groute_seed 2'),encoding='utf-8')
    drive=next(c+':' for c in 'QRSTUVWX' if not Path(c+':/').exists())
    subprocess.run(['subst',drive,str(ALT)],check=True)
    cmd=[str(PDS),'-file',drive+'/run_physical.tcl','-work_dir',drive+'/','-project_name','advanced3_seed2']
    receipt=dict(status='STARTING',started=datetime.datetime.now().astimezone().isoformat(),
                 mode='gamma_candidate_seed2',seed=2,tool=str(PDS),tool_sha256=sha(PDS),
                 source_sha256=before,constraint_sha256=identity['constraint_sha256'],script_sha256=sha(ALT/'run_physical.tcl'),
                 command=cmd,max_seconds=3600,baseline_seed7_report=identity['baseline_seed7_report'],
                 note='Exploratory second seed with identical RTL/constraints; no same-seed C50 baseline')
    save(receipt)
    start=time.monotonic()
    try:
        with (OUT/'console.log').open('wb') as log:
            proc=subprocess.Popen(cmd,cwd=ALT,env=dict(os.environ,PATH=str(PDS.parent)+os.pathsep+os.environ.get('PATH','')),
                                  stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            receipt.update(status='RUNNING',pid=proc.pid)
            save(receipt)
            print('PDS_RUNNING seed2',proc.pid,flush=True)
            while proc.poll() is None:
                elapsed=time.monotonic()-start
                receipt.update(seconds=round(elapsed,1),console_bytes=(OUT/'console.log').stat().st_size)
                save(receipt)
                if elapsed>=receipt['max_seconds']:
                    subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
                    receipt['status']='TIMEOUT';break
                time.sleep(15)
            code=proc.wait(timeout=60)
        body=(OUT/'console.log').read_text(encoding='utf-8',errors='replace')
        changed=[name for name,h in before.items() if sha(ALT/name)!=h]
        good=code==0 and 'ADV3_PHASE=FINISHED' in body and not changed
        if receipt['status']!='TIMEOUT':receipt['status']='PASS' if good else 'FAIL'
        receipt.update(exit=code,seconds=round(time.monotonic()-start,1),
                       marker_found='ADV3_PHASE=FINISHED' in body,changed_source=changed,log_sha256=sha(OUT/'console.log'))
        for name in ('hdmi_ddr_ov5640_top.prr','hdmi_ddr_ov5640_top.rtr','hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt'):
            for p in ALT.rglob(name):
                if p.is_file() and p.stat().st_size<15_000_000:
                    shutil.copy2(p,OUT/name);receipt[name+'_sha256']=sha(OUT/name);break
        save(receipt)
        print('PDS_FINISHED seed2',receipt['status'],receipt['seconds'],flush=True)
        print(body[-900:],flush=True)
        if not good:raise RuntimeError('Seed2 physical run incomplete; see receipt')
        shutil.copy2(__file__,R/Path(__file__).name)
    finally:subprocess.run(['subst',drive,'/D'],check=True)

if __name__=='__main__':main()

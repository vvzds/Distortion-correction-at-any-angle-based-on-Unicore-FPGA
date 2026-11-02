"""Run the final software suite and archive compact hash-bound evidence."""
import hashlib,json,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
tag=str(time.time_ns());start_ns=int(tag);folder=ROOT/'build/verification'/tag;folder.mkdir(parents=True)
commands=[['tools/check_map.py'],
 ['tools/check_native.py','--angle','0','--latency','40'],
 ['tools/check_native.py','--angle','45','--latency','40'],
 ['tools/check_native.py','--angle','90','--latency','40'],
 ['tools/check_native.py','--angle','90','--zoom','1.706276','--latency','40'],
 ['tools/check_native.py','--angle','0','--next-angle','45','--latency','40'],
 ['tools/check_native.py','--angle','45','--latency','40','--period','430'],
 ['tools/check_real_rtl.py'],
 ['tools/run_sim.py','host_control_tb','source/rtl/uart_phy.v','source/rtl/host_control.v','sim/host_control_tb.v'],
 ['tools/check_imu_projective_map.py'],
 ['tools/run_sim.py','adaptive_gamma_tb','source/rtl/adaptive_gamma.v','sim/adaptive_gamma_tb.v'],
 ['tools/run_sim.py','frame_ownership_tb','source/rtl/frame_bank_ctrl.v','source/rtl/corr_slot_ctrl.v','sim/frame_ownership_tb.v'],
 ['tools/check_host.py'],['tools/profile_angles.py'],['tools/check_real_images.py'],['tools/plot_quality.py']]
inputs=[p for base in ['source','host','sim','tools','calibration'] for p in (ROOT/base).rglob('*')
        if p.is_file() and p.suffix in ('.py','.v','.vh','.json') and '__pycache__' not in p.parts]
hashes={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
completed=[]
with (folder/'verify.log').open('w',encoding='utf-8') as log:
    for command in commands:
        print('Running',' '.join(command),flush=True)
        r=subprocess.run([sys.executable,*command],cwd=ROOT,capture_output=True,text=True,errors='replace')
        log.write(' '.join(command)+'\n'+r.stdout+r.stderr+'\n');log.flush()
        if r.returncode:raise SystemExit(f'FAILED: {command}; see {folder}/verify.log')
        completed.append(command)
        print('Passed',command[0],flush=True)
for key,value in hashes.items():
    if hashlib.sha256((ROOT/key).read_bytes()).hexdigest()!=value:raise SystemExit('Inputs changed during suite: '+key)
evidence=ROOT/'reports/simulation'/tag;evidence.mkdir(parents=True,exist_ok=False)
runs=[]
for receipt in (ROOT/'build/sim').glob('*/*/receipt.json'):
    if not receipt.parent.name.isdigit() or int(receipt.parent.name)<start_ns:continue
    data=json.loads(receipt.read_text())
    if not data.get('passed'):raise SystemExit('A failed simulation is present in this suite: '+str(receipt))
    dest=evidence/receipt.parent.parent.name/receipt.parent.name;dest.mkdir(parents=True)
    for name in ['run.log','inputs.json','receipt.json']:
        shutil.copy2(receipt.parent/name,dest/name)
    for name in data.get('artifacts',{}):shutil.copy2(receipt.parent/name,dest/name)
    runs.append(str(dest.relative_to(ROOT)).replace('\\','/'))
shutil.copy2(folder/'verify.log',evidence/'verify.log')
summary={'passed':True,'hardware_tested':False,'suite_id':tag,'elapsed_seconds':(time.time_ns()-start_ns)/1e9,
         'commands':completed,'simulation_runs':runs,'inputs_sha256':hashes}
(ROOT/'reports/verification_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('PASS final software suite; archived simulation runs:',len(runs))

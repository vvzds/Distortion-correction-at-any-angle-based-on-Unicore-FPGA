"""Run the final software suite and archive compact hash-bound evidence."""
import hashlib,importlib.util,json,os,shutil,subprocess,sys,time
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
 ['tools/run_sim.py','feature_config_gate_tb','source/rtl/feature_key_control.v','sim/feature_config_gate_tb.v'],
 ['tools/run_sim.py','feature_key_control_tb','source/rtl/feature_key_control.v','sim/feature_key_control_tb.v'],
 ['tools/check_imu_projective_map.py'],
 ['tools/run_sim.py','adaptive_gamma_tb','source/rtl/adaptive_gamma.v','sim/adaptive_gamma_tb.v'],
 ['tools/run_sim.py','frame_ownership_tb','source/rtl/frame_bank_ctrl.v','source/rtl/corr_slot_ctrl.v','sim/frame_ownership_tb.v'],
 ['tools/run_sim.py','affine_smooth_tb','source/rtl/projective_divide.v','source/rtl/mul32_pipe.v',
  'source/rtl/brown_map.v','source/rtl/patch_store.v','source/rtl/bilinear_rgb.v',
  'source/rtl/adaptive_gamma.v','source/rtl/tile_engine.v','sim/affine_smooth_tb.v'],
 ['tools/run_sim.py','display_denoise_tb','source/rtl/display_denoise.v','sim/display_denoise_tb.v'],
 ['tools/run_sim.py','display_sharpen_tb','source/rtl/display_sharpen.v','sim/display_sharpen_tb.v'],
 ['tools/run_sim.py','video_osd_tb','source/rtl/video_osd.v','sim/video_osd_tb.v'],
 ['tools/check_host.py'],['tools/profile_angles.py']]
photo_session=Path(os.environ.get('FPGA_PHOTO_SESSION','D:/FPGA/photo/session_203513'))
photo_manifest=photo_session/'SESSION.json'
if photo_manifest.is_file():
    try:
        photo_data=json.loads(photo_manifest.read_text(encoding='utf-8-sig'))
        held_out=[photo_session/item['path'] for item in photo_data.get('poses',[])
                  if item.get('dataset_role')=='held_out_validation']
    except (OSError,KeyError,TypeError,json.JSONDecodeError):
        held_out=[]
    if len(held_out)==5 and all(path.is_file() for path in held_out):
        commands.append(['tools/check_real_images.py','--photos',str(photo_session)])
        real_image_status='scheduled'
        if importlib.util.find_spec('matplotlib') is not None:
            commands.append(['tools/plot_quality.py'])
            quality_plot_status='scheduled'
        else:
            quality_plot_status='skipped: matplotlib is not installed in the active Python runtime'
    else:
        real_image_status='skipped: SESSION.json or one of its five held-out images is missing'
        quality_plot_status='skipped: requires a held-out real-image quality report'
else:
    real_image_status=f'skipped: held-out photo dataset not found at {photo_session}'
    quality_plot_status='skipped: requires a held-out real-image quality report'
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
         'commands':completed,'simulation_runs':runs,'inputs_sha256':hashes,
         'real_image_quality':real_image_status,'quality_plot':quality_plot_status}
(ROOT/'reports/verification_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('PASS final software suite; archived simulation runs:',len(runs))

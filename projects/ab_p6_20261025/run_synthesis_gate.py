"""Early storage/resource gate: no PnR, no full-frame simulation, no bitstream."""
from pathlib import Path
import subprocess,json,hashlib,os,datetime
from process_snapshot import snapshot
R=Path(__file__).resolve().parent;P=R/'physical/host_seed2';O=R/'results/synthesis_gate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
assert all(x['pass'] for x in load(R/'results/equivalence_p6/summary.json')['results'])
assert len(load(R/'results/negative_checks_p6/summary.json'))==11 and all(x['detected'] for x in load(R/'results/negative_checks_p6/summary.json'))
driver=(P/'synthesis_only.tcl').read_text(encoding='utf-8')
assert '\npnr ' not in driver and 'gen_bit_stream' not in driver and 'report_timing ' not in driver
inputs=load(R/'physical/input_identity.json')['inputs']
before={x['file']:sha(P/x['file']) for x in inputs}
assert all(before[x['file']]==x['sha256'] for x in inputs)
O.mkdir(parents=True,exist_ok=False)
tool=Path(r'D:\FPGA PDS\PDS_2022.2-SP6.1-win64\bin\pds_shell.exe')
env=dict(os.environ);env['PATH']=str(tool.parent)+os.pathsep+env.get('PATH','')
drive=next(c+':' for c in 'QRSTUVWXY' if not Path(c+':/').exists())
subprocess.run(['subst',drive,str(P)],check=True)
record=dict(state='RUNNING',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    source_sha256=sha(P/'source/rtl/undistort_cache_ab.v'),driver_sha256=sha(P/'synthesis_only.tcl'),input_before=before,
    thresholds=dict(tag_ram_inferred=True,minimum_tag_ram_fraction_of_p4=0.95,maximum_ff_ratio_to_p4=1.02,maximum_logic_lut_ratio_to_p4=1.05,maximum_cache_drm=12),
    tool_sha256=sha(tool),mapping=dict(drive=drive,target=str(P)))
def save():(O/'process_receipt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
try:
    cmd=[str(tool),'-file',drive+'/synthesis_only.tcl','-work_dir',drive+'/','-project_name','ab_p6_synthesis']
    record['argv']=cmd
    with (O/'console.log').open('wb') as f:
        proc=subprocess.Popen(cmd,cwd=P,env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        record['pid']=proc.pid;save();print('PDS_SYNTHESIS_RUNNING',proc.pid,flush=True)
        try:rc=proc.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            rows=snapshot();ids={proc.pid}
            while True:
                expanded=ids|{x['pid'] for x in rows if x['ppid'] in ids}
                if expanded==ids:break
                ids=expanded
            record['stopped_processes']=[x for x in rows if x['pid'] in ids]
            for target in reversed(record['stopped_processes']):
                subprocess.run(['powershell.exe','-NoProfile','-Command',f"Stop-Process -Id {target['pid']} -Force -ErrorAction SilentlyContinue"],capture_output=True)
            proc.wait(timeout=15);rc=124
    record.update(state='TIMEOUT' if rc==124 else 'FINISHED',exit_code=rc,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
finally:
    subprocess.run(['subst',drive,'/D'],check=True)
    record['changed_input_files']=[f for f,h in before.items() if not (P/f).exists() or sha(P/f)!=h]
    record['console_sha256']=sha(O/'console.log');record['bitstreams_present']=[str(p.relative_to(P)) for p in P.rglob('*.sbit')];save()
assert not record['changed_input_files'] and not record['bitstreams_present']
console=(O/'console.log').read_text(errors='replace')
def resources(root):
    p=root/'synthesize/hdmi_ddr_ov5640_top.snr'
    if not p.exists():return None
    cols=[s.strip() for s in next(s for s in p.read_text(errors='replace').splitlines() if '+ u_cache ' in s).split('|')]
    v={k:float(cols[i+2]) for i,k in enumerate(['LUT','FF','Distributed_RAM','APM','DRM'])};v['logic_LUT']=v['LUT']-v['Distributed_RAM'];return v
base=resources(R.parent/'AB_P4缓存实施_20261024/physical/host_seed2_resume_20261025');candidate=resources(P)
gates=dict(flow_completed=rc==0,no_error_lines=not any(s.startswith('E:') for s in console.splitlines()),
    tag_row_ram_inferred='Found Ram tag_row,' in console,tag_seg_ram_inferred='Found Ram tag_seg,' in console,
    distributed_ram_retained=bool(candidate and candidate['Distributed_RAM']>=base['Distributed_RAM']*0.95),
    ff_budget=bool(candidate and candidate['FF']<=base['FF']*1.02),logic_lut_budget=bool(candidate and candidate['logic_LUT']<=base['logic_LUT']*1.05),
    drm_budget=bool(candidate and candidate['DRM']<=12))
result=dict(passed=all(gates.values()),gates=gates,baseline_p4=base,candidate=candidate,
    meaning='Early resource/inference screen only; not 125MHz or complete functional acceptance',
    no_pnr_executed='Executing : pnr' not in console)
(O/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 2)

"""Read an existing P2 database into an isolated reporting directory; no design changes."""
from pathlib import Path
import subprocess,os,json,hashlib
R=Path(__file__).resolve().parent;B=R.parent/'AB_P2缓存实施_20261024/physical/host_seed2'
O=R/'results/report_api_probe';O.mkdir(exist_ok=False)
db=B/'place_route/hdmi_ddr_ov5640_top_pnr.adf'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(db)
drives=[c+':' for c in 'YXWVUTSR' if not Path(c+':/').exists()][:2];assert len(drives)==2
subprocess.run(['subst',drives[0],str(B)],check=True);subprocess.run(['subst',drives[1],str(O)],check=True)
tcl='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
tcl+=f'report_timing -input_db_file {{{drives[0]}/place_route/hdmi_ddr_ov5640_top_pnr.adf}} -from [get_cells {{u_correction/u_core/u_cache/*}}] -delay_type min_max -max_path 20 -nworst 1\nexit\n'
(O/'report.tcl').write_text(tcl,encoding='utf-8')
tool=Path(r'D:\FPGA PDS\PDS_2022.2-SP6.1-win64\bin\pds_shell.exe');env=dict(os.environ);env['PATH']=str(tool.parent)+os.pathsep+env.get('PATH','')
cmd=[str(tool),'-file',drives[1]+'/report.tcl','-work_dir',drives[1]+'/','-project_name','report_probe']
try:
    with (O/'console.log').open('wb') as f:rc=subprocess.run(cmd,cwd=O,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW).returncode
finally:
    for d in reversed(drives):subprocess.run(['subst',d,'/D'],check=True)
assert sha(db)==before
body=(O/'console.log').read_text(errors='replace')
receipt=dict(exit_code=rc,input_db=str(db),input_sha256=before,input_unchanged=sha(db)==before,argv=cmd,
    synthesis_or_pnr_executed=any('Executing : '+s in body for s in ('compile','synthesize','pnr','dev_map')),
    errors=[s for s in body.splitlines() if s.startswith('E:')])
(O/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(receipt,indent=2));print(body[-2200:])

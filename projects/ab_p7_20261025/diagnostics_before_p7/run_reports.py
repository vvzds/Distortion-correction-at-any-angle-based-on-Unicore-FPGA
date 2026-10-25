"""Read existing immutable mapped/routed databases; never build or alter RTL."""
from pathlib import Path
import subprocess,os,json,hashlib,re,datetime
from concurrent.futures import ThreadPoolExecutor
R=Path(__file__).resolve().parent;W=R.parent;O=R/'results';O.mkdir(parents=True,exist_ok=True)
P4=W/'AB_P4缓存实施_20261024/physical/host_seed2_resume_20261025'
P2=W/'AB_P2缓存实施_20261024/physical/host_seed2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
jobs=[('p4_mapped_match',P4/'device_map/hdmi_ddr_ov5640_top_map.adf','match_*'),
      ('p4_mapped_qid',P4/'device_map/hdmi_ddr_ov5640_top_map.adf','qid*'),
      ('p2_routed_match',P2/'place_route/hdmi_ddr_ov5640_top_pnr.adf','match_*'),
      ('p2_routed_qid',P2/'place_route/hdmi_ddr_ov5640_top_pnr.adf','qid*')]
drives=[c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists()][:3];assert len(drives)==3
for drive,p in zip(drives,(P4,P2,R)):subprocess.run(['subst',drive,str(p)],check=True)
tool=Path(r'D:\FPGA PDS\PDS_2022.2-SP6.1-win64\bin\pds_shell.exe');env=dict(os.environ);env['PATH']=str(tool.parent)+os.pathsep+env.get('PATH','')
before={str(p):sha(p) for _,p,_ in jobs}
def run(job):
    name,db,pattern=job;d=O/name;d.mkdir(exist_ok=False)
    drive=drives[0] if name.startswith('p4') else drives[1]
    root=P4 if name.startswith('p4') else P2
    mapped=drive+'/'+db.relative_to(root).as_posix()
    tcl='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
    tcl+=f'report_timing -input_db_file {{{mapped}}} -to [get_cells {{u_correction/u_core/u_cache/{pattern}}}] -delay_type min_max -max_path 20 -nworst 1\nexit\n'
    (d/'report.tcl').write_text(tcl,encoding='utf-8')
    cmd=[str(tool),'-file',drives[2]+'/results/'+name+'/report.tcl','-work_dir',drives[2]+'/results/'+name+'/', '-project_name',name]
    with (d/'console.log').open('wb') as log:
        p=subprocess.run(cmd,cwd=d,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
    console=(d/'console.log').read_text(errors='replace')
    assert not any('Executing : '+s in console for s in ('compile','synthesize','pnr','dev_map'))
    files=list((d/'report_timing').glob('*.rtr'));paths=[]
    if files:
        for b in files[0].read_text(errors='replace').split('Startpoint  :')[1:]:
            en=re.search(r'^Endpoint\s+: (.+)$',b,re.M);ty=re.search(r'^Path Type\s+: (.+)$',b,re.M);sl=re.search(r'Slack \((?:MET|VIOLATED)\)\s+(-?[\d.]+)',b)
            if not (en and ty and sl):continue
            row=dict(start=b.splitlines()[0].strip(),end=en[1].strip(),type=ty[1].strip(),slack_ns=float(sl[1]))
            dl=re.search(r'Logic:\s*([\d.]+)ns\([^)]*\), Route:\s*([\d.]+)ns',b)
            if dl:row.update(logic_ns=float(dl[1]),route_ns=float(dl[2]))
            row['path_text']=b[:b.index('slack')+100] if 'slack' in b else b
            paths.append(row)
    errors=[s for s in console.splitlines() if s.startswith('E:')]
    selected=bool(paths) and all(x['end'].startswith('u_correction/u_core/u_cache/'+pattern.rstrip('*')) for x in paths)
    result=dict(exit_code=p.returncode,argv=cmd,input_db=str(db),input_sha256=before[str(db)],input_unchanged=sha(db)==before[str(db)],
                source_version='P4 mapped estimate (no route)' if name.startswith('p4') else 'Historical P2 routed evidence; not a new candidate',
                errors=errors,selected_endpoints_match=selected,paths=paths,report_sha256=sha(files[0]) if files else None,
                synthesis_or_pnr_executed=False,kinds={k:min(x['slack_ns'] for x in paths if x['type']==k) for k in {x['type'] for x in paths}})
    (d/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(name,json.dumps(dict(rc=p.returncode,paths=len(paths),selected=selected,kinds=result['kinds'],errors=errors)),flush=True)
    return result
try:
    with ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(run,jobs))
finally:
    for drive in reversed(drives):subprocess.run(['subst',drive,'/D'],check=True)
    assert all(sha(Path(p))==h for p,h in before.items())
(O/'reports_summary.json').write_text(json.dumps(dict(original_databases_unchanged=True,results=results),ensure_ascii=False,indent=2),encoding='utf-8')
assert all(x['exit_code']==0 and not x['errors'] and x['selected_endpoints_match'] for x in results)

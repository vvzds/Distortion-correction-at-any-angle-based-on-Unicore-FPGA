"""Read the completed P7 PnR database; write each filtered report separately."""
from pathlib import Path
import subprocess,json,hashlib,os,re,datetime
from process_snapshot import snapshot
R=Path(__file__).resolve().parent;P=R/'physical/host_seed2';O=R/'results/focused_diagnostic'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
run=load(R/'results/physical_seed2/process_receipt.json')
assert run['state']=='FINISHED' and run['exit_code']==0
assert not run['changed_input_files'] and not run['bitstreams_present']
# Read-only report API was verified independently; every run also checks no build command executed.
db=P/'place_route/hdmi_ddr_ov5640_top_pnr.adf';assert db.exists()
originals=[db,P/'report_timing/hdmi_ddr_ov5640_top.rtr',P/'place_route/hdmi_ddr_ov5640_top.prr',P/'multiseed_summary.csv']
before={str(p.relative_to(R)):sha(p) for p in originals}
O.mkdir(exist_ok=False)
tool=Path(r'D:\FPGA PDS\PDS_2022.2-SP6.1-win64\bin\pds_shell.exe')
env=dict(os.environ);env['PATH']=str(tool.parent)+os.pathsep+env.get('PATH','')
drive=next(c+':' for c in 'YXWVUTSR' if not Path(c+':/').exists())
subprocess.run(['subst',drive,str(R)],check=True)
results={}
try:
    for name,side,module in [('tag_match','to','match'),('age_update','to','last_use'),('victim_group','to','victim_age'),('victim_final','to','chosen')]:
        d=O/name;d.mkdir();rel=d.relative_to(R).as_posix();prefix='u_correction/u_core/u_cache/'+module
        text='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        text+=f'report_timing -input_db_file {{{drive}/physical/host_seed2/place_route/hdmi_ddr_ov5640_top_pnr.adf}} -{side} [get_cells {{{prefix}*}}] -delay_type min_max -max_path 20 -nworst 1\nexit\n'
        (d/'report.tcl').write_text(text,encoding='utf-8')
        cmd=[str(tool),'-file',drive+'/'+rel+'/report.tcl','-work_dir',drive+'/'+rel+'/', '-project_name',name]
        with (d/'console.log').open('wb') as f:
            proc=subprocess.Popen(cmd,cwd=d,env=env,stdout=f,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            try:rc=proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                rows=snapshot();owned={proc.pid}
                while True:
                    expanded=owned|{x['pid'] for x in rows if x['ppid'] in owned}
                    if expanded==owned:break
                    owned=expanded
                for target in reversed([x for x in rows if x['pid'] in owned]):
                    subprocess.run(['powershell.exe','-NoProfile','-Command',f"Stop-Process -Id {target['pid']} -Force -ErrorAction SilentlyContinue"],capture_output=True)
                rc=124
        console=(d/'console.log').read_text(errors='replace')
        assert not any('Executing : '+s in console for s in ('compile','synthesize','pnr','dev_map')),'Report-only action unexpectedly executed build'
        report=d/'report_timing/hdmi_ddr_ov5640_top.rtr';paths=[]
        if report.exists():
            body=report.read_text(errors='replace')
            for block in body.split('Startpoint  :')[1:]:
                sl=re.search(r'Slack \((?:MET|VIOLATED)\)\s+(-?[\d.]+)',block);en=re.search(r'^Endpoint\s+: (.+)$',block,re.M);pt=re.search(r'^Path Type\s+: (.+)$',block,re.M)
                if not (sl and en and pt):continue
                row=dict(start=block.splitlines()[0].strip(),end=en[1].strip(),type=pt[1].strip(),slack_ns=float(sl[1]))
                delays=re.search(r'Logic:\s*([\d.]+)ns\([^)]*\), Route:\s*([\d.]+)ns',block)
                if delays:row.update(logic_ns=float(delays[1]),route_ns=float(delays[2]))
                paths.append(row)
        match=bool(paths) and all(x['start' if side=='from' else 'end'].startswith(prefix) for x in paths)
        kinds={x['type'] for x in paths};coverage=kinds=={'max (slow corner)','max (fast corner)','min (slow corner)','min (fast corner)'}
        errors=[s for s in console.splitlines() if s.startswith('E:')]
        good=rc==0 and not errors and match and coverage
        verdict='FAIL' if good and any(x['slack_ns']<0 for x in paths) else ('PASS_UNDER_EXISTING_CONSTRAINTS' if good else 'REQUIRES_COVERAGE_REVIEW')
        result=dict(verdict=verdict,exit_code=rc,argv=cmd,report=report.relative_to(R).as_posix(),sha256=sha(report) if report.exists() else None,
            selected_side=side,selection_prefix=prefix,all_selected_endpoints_match=match,four_check_corner_types_present=coverage,errors=errors,
            kinds={k:dict(count=sum(x['type']==k for x in paths),worst_slack_ns=min(x['slack_ns'] for x in paths if x['type']==k)) for k in sorted(kinds)},
            worst_paths=sorted(paths,key=lambda x:x['slack_ns'])[:8])
        results[name]=result;(d/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,verdict,result['kinds'],flush=True)
finally:
    subprocess.run(['subst',drive,'/D'],check=True)
    after={str(p.relative_to(R)):sha(p) for p in originals}
    assert after==before,'Original native evidence or database changed'
out=dict(focused_reports=results,original_inputs_before=before,original_inputs_after=after,original_evidence_unchanged=True,
    scope='Read-only diagnostic subsets in this completed P7R1 PNR DB; tag match, age update and victim selection. Not a replacement for complete cache closure.',
    checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(R/'results/focused_diagnostic.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')

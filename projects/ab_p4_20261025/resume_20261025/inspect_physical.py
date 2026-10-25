"""Extract native evidence without equating tool exit status with timing closure."""
from pathlib import Path
import re,json,hashlib
R=Path(__file__).resolve().parent.parent
B=R/'baseline/physical'
C=R/'physical/host_seed2_resume_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return p.read_text(encoding='utf-8',errors='replace')
def extract(root):
    files={k:root/f'{folder}/hdmi_ddr_ov5640_top.{ext}' for k,folder,ext in [('synthesis','synthesize','snr'),('map','device_map','dmr'),('pnr','place_route','prr'),('timing','report_timing','rtr')]}
    text={k:read(p) for k,p in files.items()}
    resources={}
    for stage in ['synthesis','pnr']:
        rows={}
        for line in text[stage].splitlines():
            cols=[s.strip() for s in line.split('|')]
            if len(cols)>6 and (cols[1]=='hdmi_ddr_ov5640_top' or cols[1].lstrip('+ ').strip() in ('u_core','u_cache')):
                rows[cols[1]]={name:float(cols[i+2]) for i,name in enumerate(['LUT','FF','Distributed_RAM','APM','DRM'])}
        resources[stage]=rows
    # Global summary table must equal the hierarchy root (no rounding tolerance).
    pnr=text['pnr'].split('Device Utilization Summary :',1)[1].split('Device Utilization Summary Of Each Module:',1)[0]
    global_counts={}
    for key,pattern in [('LUT',r'^\|\s+LUT\s+\|\s*([\d.]+)'),('FF',r'^\|\s+FF\s+\|\s*([\d.]+)'),('APM',r'^\| Use of APM\s+\|\s*([\d.]+)'),('DRM',r'^\| Use of DRM\s+\|\s*([\d.]+)'),('Distributed_RAM',r'^\|\s+Distributed RAM\s+\|\s*([\d.]+)')]:
        vals=re.findall(pattern,pnr,re.M);assert vals,key
        global_counts[key]=sum(float(v) for v in vals)
    tables_match=global_counts==resources['pnr']['hdmi_ddr_ov5640_top']
    timing=[]
    for match in re.finditer(r'^(Setup|Hold) Summary\((Slow|Fast) Corner\):\s*\n(.*?)(?=\n\s*\n)',text['timing'],re.M|re.S):
        rows=[]
        for line in match[3].splitlines():
            parts=line.split()
            if len(parts)==6:
                try:rows.append({'launch':parts[0],'capture':parts[1],'slack_ns':float(parts[2]),'total_slack_ns':float(parts[3]),'failing_endpoints':int(parts[4]),'endpoints':int(parts[5])})
                except ValueError:pass
        if rows:timing.append({'kind':match[1],'corner':match[2],'worst_slack_ns':min(x['slack_ns'] for x in rows),'rows':rows})
    paths=[]
    for block in text['timing'].split('Startpoint  :')[1:]:
        sl=re.search(r'Slack \((?:MET|VIOLATED)\)\s+(-?[\d.]+)',block)
        en=re.search(r'^Endpoint\s+: (.+)$',block,re.M)
        pt=re.search(r'^Path Type\s+: (.+)$',block,re.M)
        if sl and en and pt:
            delays=re.search(r'Logic:\s*([\d.]+)ns\([^)]*\), Route:\s*([\d.]+)ns',block)
            row={'start':block.splitlines()[0].strip(),'end':en[1].strip(),'type':pt[1].strip(),'slack_ns':float(sl[1])}
            if delays:
                row.update(logic_ns=float(delays[1]),route_ns=float(delays[2]),data_delay_ns=round(float(delays[1])+float(delays[2]),3))
            paths.append(row)
    worst=sorted(paths,key=lambda p:p['slack_ns'])[:20]
    categories={key:sorted([p for p in paths if any(s in p['start']+' '+p['end'] for s in terms)],key=lambda p:p['slack_ns'])[:3]
                for key,terms in {'mask':['done_mask'],'qid':['/qid['],'touch':['touch'],'timestamps':['last_use'],'map':['/u_map/'],'victim':['chosen','best_age','eligible']}.items()}
    warnings=[]
    for p in root.rglob('*.log'):
        for no,line in enumerate(read(p).splitlines(),1):
            if re.search(r'^\s*[WEC]:|\b(?:WARN(?:ING)?|ERROR|CRITICAL)\b',line,re.I):warnings.append({'file':p.relative_to(root).as_posix(),'line':no,'text':line})
    return {'native_reports':{k:{'path':p.relative_to(root).as_posix(),'sha256':sha(p)} for k,p in files.items()},'resources':resources,'pnr_global_resources':global_counts,'pnr_two_tables_match':tables_match,'timing_summary':timing,'worst_reported_paths':worst,'reported_path_categories':categories,'warning_log_lines':warnings,'note':'Only paths emitted by the native report are included; absence is not proof that an unreported path disappeared.'}
result={'baseline':extract(B),'candidate':extract(C)}
expected_groups={('Setup','Slow'),('Setup','Fast'),('Hold','Slow'),('Hold','Fast')}
for item in result.values():
    assert {(t['kind'],t['corner']) for t in item['timing_summary']}==expected_groups,'Incomplete or unexpected timing groups'
    assert len(item['timing_summary'])==4,'Duplicated timing groups require review'
result['all_reported_setup_hold_nonnegative']=all(t['worst_slack_ns']>=0 for t in result['candidate']['timing_summary'])
assert len(result['candidate']['timing_summary'])>=4
(R/'results/physical_comparison_20261025.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{'resources':v['resources'],'tables_match':v['pnr_two_tables_match'],'timing':[{a:t[a] for a in ('kind','corner','worst_slack_ns')} for t in v['timing_summary']],'worst_paths':v['worst_reported_paths'][:3]} for k,v in result.items() if isinstance(v,dict)},ensure_ascii=False,indent=2))

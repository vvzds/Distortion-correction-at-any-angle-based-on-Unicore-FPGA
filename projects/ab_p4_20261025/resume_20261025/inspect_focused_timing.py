"""Conservatively classify focused reports; absence never means timing closure."""
from pathlib import Path
import hashlib,json,re
R=Path(__file__).resolve().parent.parent
P=R/'physical/host_seed2_resume_20261025'
console=(R/'results/physical_seed2_resume_20261025/console.log').read_text(errors='replace')
assert 'P4_UNRESTRICTED_REPORT_RESTORED' in console
prefix='u_correction/u_core/u_cache/'
results={}
for name in ['map','cache_from','cache_to']:
    p=P/f'report_timing_{name}_diagnostic/hdmi_ddr_ov5640_top.rtr'
    item={'completed_marker':f'P4_{name.upper()}_DIAG_COMPLETED' in console,
          'path':str(p.relative_to(R)), 'exists':p.exists()}
    paths=[]
    if p.exists():
        body=p.read_text(errors='replace')
        item['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        item['command']=next((s.strip() for s in body.splitlines() if 'Tcl Command' in s),'')
        for block in body.split('Startpoint  :')[1:]:
            end=re.search(r'^Endpoint\s+: (.+)$',block,re.M)
            typ=re.search(r'^Path Type\s+: (.+)$',block,re.M)
            sl=re.search(r'Slack \((?:MET|VIOLATED)\)\s+(-?[\d.]+)',block)
            if not (end and typ and sl):continue
            row={'start':block.splitlines()[0].strip(),'end':end[1].strip(),
                 'type':typ[1].strip(),'slack_ns':float(sl[1])}
            delay=re.search(r'Logic:\s*([\d.]+)ns\([^)]*\), Route:\s*([\d.]+)ns',block)
            if delay:row.update(logic_ns=float(delay[1]),route_ns=float(delay[2]))
            paths.append(row)
    matchprefix='u_correction/u_core/u_map/' if name=='map' else prefix
    side='end' if name=='cache_to' else 'start'
    item['reported_paths']=len(paths)
    item['all_reported_endpoints_match_selection']=bool(paths) and all(x[side].startswith(matchprefix) for x in paths)
    groups={}
    for row in paths:groups.setdefault(row['type'],[]).append(row)
    item['path_groups']={key:{'reported':len(rows),'worst_slack_ns':min(x['slack_ns'] for x in rows),'worst_paths':sorted(rows,key=lambda x:x['slack_ns'])[:5]} for key,rows in groups.items()}
    item['negative_reported_paths']=sum(x['slack_ns']<0 for x in paths)
    # Inspect actual native group labels before ever turning a nonnegative report
    # into a cache pass. A successful tool exit/no paths is insufficient.
    item['verdict']='FAIL' if any(x['slack_ns']<0 for x in paths) and item['all_reported_endpoints_match_selection'] else 'REQUIRES_COVERAGE_REVIEW'
    results[name]=item
out={'scope':'Cache internal and crossing endpoints; core throughput owned by collaborator 02',
     'focused_reports':results,'cache_closure':'FAIL' if any(results[n]['verdict']=='FAIL' for n in ['cache_from','cache_to']) else 'REQUIRES_COVERAGE_REVIEW',
     'note':'Unrestricted CSV/report retains system verdict. Focused report global summaries may remain global; classify actual matching paths, verify corner/check coverage before PASS.'}
(R/'results/focused_timing_20261025.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))

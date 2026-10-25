"""Establish cache status from actual matching paths, never tool exit alone."""
from pathlib import Path
import re,json,hashlib
N=Path(__file__).resolve().parent;R=N.parent
P=R/'physical/host_seed2_resume_20261025'
prefix='u_correction/u_core/u_cache/'
rows=[];sources=[]
for name,folder,side in [('unrestricted','report_timing',None),('cache_from','report_timing_cache_from_diagnostic','start'),('cache_to','report_timing_cache_to_diagnostic','end')]:
    p=P/folder/'hdmi_ddr_ov5640_top.rtr'
    if not p.exists():sources.append({'name':name,'exists':False});continue
    body=p.read_text(errors='replace');paths=[]
    for block in body.split('Startpoint  :')[1:]:
        end=re.search(r'^Endpoint\s+: (.+)$',block,re.M);typ=re.search(r'^Path Type\s+: (.+)$',block,re.M)
        slack=re.search(r'Slack \((?:MET|VIOLATED)\)\s+(-?[\d.]+)',block)
        if not(end and typ and slack):continue
        row={'start':block.splitlines()[0].strip(),'end':end[1].strip(),'type':typ[1].strip(),'slack_ns':float(slack[1]),'report':name}
        if prefix in row['start'] or prefix in row['end']:rows.append(row)
        paths.append(row)
    sources.append({'name':name,'exists':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                    'selection_matches':bool(paths) and (side is None or all(x[side].startswith(prefix) for x in paths)),
                    'all_types':sorted({x['type'] for x in paths}),
                    'cache_types':sorted({x['type'] for x in paths if prefix in x['start'] or prefix in x['end']}),
                    'paths_reported':len(paths)})
negative=sorted([x for x in rows if x['slack_ns']<0],key=lambda x:x['slack_ns'])
expected={'max (slow corner)','min (slow corner)','max (fast corner)','min (fast corner)'}
focused=[s for s in sources if s['name']!='unrestricted']
covered=len(focused)==2 and all(s.get('selection_matches') and expected<=set(s.get('cache_types',[])) for s in focused)
status='FAIL' if negative else ('PASS_REQUIRES_NATIVE_SELECTION_REVIEW' if covered else 'NOT_ESTABLISHED')
out={'cache_status':status,'all_four_setup_hold_groups_reported_in_both_directions':covered,
     'negative_cache_paths':negative[:20],'reported_cache_path_count':len(rows),'report_sources':sources,
     'scope':'Cache registers and boundary paths as selected by emitted native reports; whole-system status uses unrestricted report+CSV. A negative observed path is sufficient to reject; PASS still requires verifying matched get_cells object coverage.',
     'exclusions':'No claim about unconstrained IO, board functionality, core throughput or omitted timing checks.'}
(R/'results/cache_timing_review_20261025.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))

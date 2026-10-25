from pathlib import Path
import re,json,hashlib,collections
R=Path(__file__).resolve().parent.parent
paths={'R0':R/'baseline/physical/execution/console_full.log','P4':R/'results/physical_seed2_resume_20261025/console.log'}
data={}
for name,p in paths.items():
    lines=[l for l in p.read_text(encoding='utf-8',errors='replace').splitlines() if re.match(r'^[WEC]:',l)]
    counts=collections.Counter();examples={}
    for l in lines:
        m=re.match(r'^([WEC]):\s+([A-Za-z]+-\d+):',l)
        code=':'.join(m.groups()) if m else 'UNCODED:'+l.split(':',1)[1].strip().split(' inst ',1)[0].split(' for ',1)[0][:70]
        counts[code]+=1
        if code not in examples:examples[code]=l
    data[name]={'file':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'counts':dict(counts),'examples':examples,'error_count':sum(l.startswith('E:') for l in lines),'critical_count':sum(l.startswith('C:') for l in lines),'last_use_feedback_count':sum('Sdm-2014:' in l and "signal 'last_use" in l for l in lines),'lines':lines}
codes=sorted(data['R0']['counts'].keys()|data['P4']['counts'].keys())
rows=[{'category':k,'R0':data['R0']['counts'].get(k,0),'P4':data['P4']['counts'].get(k,0)} for k in codes]
new=set(data['P4']['lines'])-set(data['R0']['lines'])
suspect=sorted(l for l in new if re.search(r'(?i)latch|multiple.driver|multi.driver|truncat|width.mismatch|unsupported|illegal|conflict|unconn|not driven',l))
for d in data.values():del d['lines']
out={'evidence':data,'counts':rows,'new_unique_keyword_hits':suspect,'scope':'Relative console-log triage only; not a full-design safety proof. Native warnings retained, not waived.'}
(R/'results/warning_comparison_20261025.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'coded_categories':[x for x in rows if not x['category'].startswith('UNCODED')],'new_unique_keyword_hit_count':len(suspect),'last_use_feedback':{k:v['last_use_feedback_count'] for k,v in data.items()},'error_counts':{k:v['error_count'] for k,v in data.items()},'critical_counts':{k:v['critical_count'] for k,v in data.items()}},ensure_ascii=False,indent=2))

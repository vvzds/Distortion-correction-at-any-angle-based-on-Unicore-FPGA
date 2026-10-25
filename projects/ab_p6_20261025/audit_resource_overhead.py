"""Count final synthesis primitive names, not early feedback-mux warnings."""
from pathlib import Path
import re,json,collections,hashlib
R=Path(__file__).resolve().parent;W=R.parent
roots={'P4':W/'AB_P4缓存实施_20261024/physical/host_seed2_resume_20261025',
       'P6':W/'AB_P6标签RAM与局部替换_20261025/physical/host_seed2',
       'P6R1':R/'physical/host_seed2'}
out={}
for name,root in roots.items():
    p=root/'synthesize/hdmi_ddr_ov5640_top_syn.vm';text=p.read_text()
    counts=collections.Counter();modules=[]
    for m in re.finditer(r'(?m)^module ([^\n]+)\n([\s\S]*?)^endmodule',text):
        if not any(x in m[1] for x in ('undistort_cache','undistort_age')):continue
        local=collections.Counter()
        for f in re.finditer(r'GTP_DFF\w*\s+/\*\s*(.*?)\s*\*/',m[2]):
            n=f[1].strip('\\ ')
            if 'last_use[' in n or re.search(r'(?:\.|^|/)age\[',n):key='age'
            elif 'victim_leaf[' in n or re.search(r'(?:\.|^|/)leaf\[',n):key='leaf'
            elif 'victim_age[' in n:key='winner_age'
            elif re.search(r'(?:\.|^|/)winner\[',n):
                bit=int(re.search(r'winner\[(\d+)\]',n)[1]);key='winner_age' if 8<=bit<=29 else 'winner_other'
            elif 'victim_hit[' in n or 'victim_id[' in n:key='winner_other'
            elif 'done_mask[' in n or re.search(r'(?:\.|^|/)mask\[',n):key='mask'
            else:key='other'
            local[key]+=1
        modules.append(dict(module=m[1],count=sum(local.values()),categories=dict(local)))
        counts.update(local)
    out[name]=dict(netlist=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),ff=sum(counts.values()),categories=dict(counts),modules=modules)
out['diagnosis']=dict(original_extra_ff=out['P6']['ff']-out['P4']['ff'],
    original_category_delta={k:out['P6']['categories'].get(k,0)-out['P4']['categories'].get(k,0) for k in out['P6']['categories']},
    revision_extra_ff=out['P6R1']['ff']-out['P4']['ff'],
    meaning='Counts from generated GTP_DFF primitives; full 22-bit RTL remains and F13 exercises nonzero MSB in standalone simulation')
(R/'results/resource_overhead_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k=='diagnosis'},indent=2))

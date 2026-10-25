"""Structural cache netlist fanout and combinational-cone census, no RTL edits."""
from pathlib import Path
import re,json,hashlib,collections,sys
R=Path(__file__).resolve().parent;W=R.parent;O=R/'results';O.mkdir(exist_ok=True)
P=W/'AB_P4缓存实施_20261024/physical/host_seed2_resume_20261025/synthesize/hdmi_ddr_ov5640_top_syn.vm'
s=P.read_text();a=s.index('\nmodule undistort_cache_ab\n');b=s.index('\nendmodule',a);s=s[a:b]
# Use anchored splits rather than unbounded regex across a multi-MB netlist.
starts=list(re.finditer(r'^    (GTP_\w+)\s+/\*\s*(.*?)\s*\*/',s,re.M));cells=[]
for i,m in enumerate(starts):
    text=s[m.start():starts[i+1].start() if i+1<len(starts) else len(s)]
    # Port assignments have a whitespace separator; parameter assignments do not.
    ports={p:v.strip() for p,v in re.findall(r'\.(\w+)\s+\(([^()]*)\)',text)}
    cells.append(dict(type=m[1],name=m[2].strip('\\ '),ports=ports))
assert cells and all(x['ports'] for x in cells)
const=re.compile(r"\d+'[bhd][0-9a-fxz]+",re.I)
token=re.compile(r'\\[^\s,{}]+|[A-Za-z_$][\w$]*(?:\[\d+\])*(?:\[\d+:\d+\])?')
def nets(expr):return token.findall(const.sub('',expr))
def outputs(c):
    t=c['type']
    if t.startswith('GTP_DFF'):return {'Q','QN'}
    if t.startswith('GTP_RAM'):return {'DO','SPO','DPO'}
    if t.startswith('GTP_DRM'):return {'DOA','DOB'}
    return {'Z','Z0','Z1','O','F','S','CO','COUT','SUM','Y'}
fan=collections.defaultdict(list);drivers={}
for i,c in enumerate(cells):
    outs=outputs(c)
    for pin,expr in c['ports'].items():
        for n in nets(expr):
            if pin in outs:drivers[n]=i
            else:fan[n].append((i,pin))
ram=[c for c in cells if c['type'].startswith('GTP_RAM') and c['name'].startswith(('tag_row','tag_seg'))]
ram_summary=collections.Counter((c['type'],c['name'].split('_')[1]) for c in ram)
addr=collections.Counter(c['ports'].get('RADDR','') for c in ram)
sequential=lambda c:c['type'].startswith(('GTP_DFF','GTP_RAM','GTP_DRM'))
memo={};cycles=[]
def depth(n,active=frozenset()):
    if n in memo:return memo[n]
    if n not in drivers:return (0,n,[])
    i=drivers[n];c=cells[i]
    if sequential(c):return (0,c['name'],[])
    if n in active:cycles.append(n);return (0,'CYCLE',[])
    candidates=[depth(v,active|{n}) for pin,expr in c['ports'].items() if pin not in outputs(c) for v in nets(expr)]
    base=max(candidates,key=lambda x:x[0]) if candidates else (0,n,[])
    result=(base[0]+1,base[1],base[2]+[dict(cell=c['name'],type=c['type'])]);memo[n]=result;return result
cones=[]
for c in cells:
    if c['type'].startswith('GTP_DFF') and c['name'].startswith(('match_id','match_hit','qid','qfound')):
        for pin in ('D','CE'):
            if pin not in c['ports']:continue
            ds=[depth(n) for n in nets(c['ports'][pin])]
            if ds:
                d=max(ds,key=lambda x:x[0]);cones.append(dict(endpoint=c['name']+'/'+pin,levels=d[0],start=d[1],cells=d[2]))
top=[]
for n,loads in sorted(fan.items(),key=lambda x:len(x[1]),reverse=True)[:50]:
    c=cells[drivers[n]] if n in drivers else None
    top.append(dict(net=n,pin_loads=len(loads),driver=c['name'] if c else 'module input/alias',
                    driver_type=c['type'] if c else None,sink_types=dict(collections.Counter(cells[i]['type'] for i,_ in loads)),
                    example_loads=[dict(cell=cells[i]['name'],pin=p) for i,p in loads[:8]]))
out=dict(netlist=str(P),sha256=hashlib.sha256(P.read_bytes()).hexdigest(),primitive_count=len(cells),
    primitive_types=dict(collections.Counter(c['type'] for c in cells)),
    tag_ram_count=len(ram),tag_ram_types=[dict(type=k[0],field=k[1],count=v) for k,v in ram_summary.items()],
    tag_ram_read_addresses=[dict(expression=k,count=v) for k,v in addr.most_common(20)],
    top_local_pin_fanouts=top,deepest_match_select_cones=sorted(cones,key=lambda x:x['levels'],reverse=True)[:30],
    combinational_cycle_net_names=sorted(set(cycles)),
    limitations='Within cache module only; input aliases and vector expansion are not elaborated. Primitive pin loads and unweighted logic-depth diagnostics are not STA or physical fanout/delay measurements.')
(O/'netlist_diagnosis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(primitives=len(cells),tag_ram=len(ram),addr_top=out['tag_ram_read_addresses'][:5],fanout_top=top[:5],deepest=out['deepest_match_select_cones'][:4]),ensure_ascii=False,indent=2))

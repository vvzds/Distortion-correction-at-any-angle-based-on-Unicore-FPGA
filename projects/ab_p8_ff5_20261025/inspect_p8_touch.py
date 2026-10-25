from pathlib import Path
import re,json,collections,hashlib
W=Path(r'C:\Users\lenovo\Desktop\ww');R=W/'AB_P8触摸译码局部化_20261025';B=W/'AB_P7R1标签RAM与共享比较_20261025'
def measure(p):
    text=p.read_text();a=text.index('\nmodule undistort_cache_ab\n');b=text.index('\nendmodule',a);text=text[a:b]
    starts=list(re.finditer(r'^    (GTP_\w+)\s+/\*\s*(.*?)\s*\*/',text,re.M))
    cells=[];loads=collections.Counter();drivers={}
    token=re.compile(r'\\[^\s,{}]+(?:\s+\[\d+\])?|[A-Za-z_$][\w$]*(?:\[\d+\])*')
    outputs={'Q','QN','DO','SPO','DPO','Z','Z0','Z1','O','F','S','CO','COUT','SUM','Y'}
    def nets(expr):return [re.sub(r'\s+','',n.lstrip('\\')) for n in token.findall(re.sub(r"\d+'[bhd][0-9a-fxz]+",'',expr,flags=re.I))]
    for i,m in enumerate(starts):
        block=text[m.start():starts[i+1].start() if i+1<len(starts) else len(text)]
        ports={pin:v.strip() for pin,v in re.findall(r'\.(\w+)\s+\(([^()]*)\)',block)}
        c=dict(type=m[1],name=m[2].strip('\\ '),ports=ports);cells.append(c)
        for pin,expr in ports.items():
            for net in nets(expr):
                if pin in outputs:drivers[net]=dict(type=c['type'],name=c['name'],pin=pin,ports=ports)
                else:loads[net]+=1
    qualifiers={n:dict(pin_loads=loads[n],driver=drivers.get(n)) for n in sorted(loads|drivers.keys()) if re.fullmatch(r'touch_bank\[\d+\]\.touch[0-3]',n)}
    return dict(netlist=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        qualifier_count=len(qualifiers),qualifiers=qualifiers,input_touch_pin_loads=loads['i_touch'],
        largest_control_loads=loads.most_common(15),
        limitations='Synthesis primitive pin loads within cache only; these are not physical fanout or timing results.')
result={}
for label,root in [('p7r1',B),('p8',R)]:
    result[label]=measure(root/'physical/host_seed2/synthesize/hdmi_ddr_ov5640_top_syn.vm')
result['all_48_qualifiers_preserved']=result['p8']['qualifier_count']==48
out=R/'results/synthesis_gate/touch_network.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:dict(qualifier_count=v['qualifier_count'],input_touch_pin_loads=v['input_touch_pin_loads'],qualifier_load_min=min((q['pin_loads'] for q in v['qualifiers'].values()),default=0),qualifier_load_max=max((q['pin_loads'] for q in v['qualifiers'].values()),default=0)) for k,v in result.items() if isinstance(v,dict)},indent=2))

"""Compare actual synthesized cache timestamp cones (not RTL estimates)."""
from pathlib import Path
import re,json,hashlib
R=Path(__file__).resolve().parent
def parse(p):
    raw=p.read_text(errors='replace')
    t=raw.split('module undistort_cache_ab',1)[1].split('endmodule',1)[0]
    cells=[];drivers={}
    for m in re.finditer(r'\b(GTP_\w+)\s+/\*\s*(.*?)\s*\*/\s*#\((.*?)\);',t,re.S):
        kind,name,body=m.groups()
        ports=dict(re.findall(r'\.(\w+)\s*\(\s*([^()]*)\s*\)',body))
        ports={k:re.sub(r'\s+','',v) for k,v in ports.items()}
        cell={'type':kind,'name':name.strip(),'ports':ports}
        cells.append(cell)
        for out in ['Z','Z5','Q']:
            if out in ports:drivers[ports[out]]=cell
    def trace(net,target,seen=()):
        if net==target:return []
        if net in seen:return None
        c=drivers.get(net)
        if c is None or not c['type'].startswith('GTP_LUT'):return None
        paths=[]
        for port,value in c['ports'].items():
            if not re.fullmatch(r'I\d+',port):continue
            path=trace(value,target,seen+(net,))
            if path is not None:paths.append(path+[{'cell':c['name'],'type':c['type'],'input':port,'output_net':net,'init':c['ports'].get('INIT')}])
        return max(paths,key=len) if paths else None
    rows=[]
    for slot in [0,99,163]:
        ff=next(c for c in cells if re.sub(r'\s+','',c['name'])==f'\\last_use[{slot}][1]')
        cone={}
        for port in ['CE','D']:
            net=ff['ports'][port];path=trace(net,'i_touch')
            cone[port]={'net':net,'driver':drivers.get(net),'touch_lut_depth':None if path is None else len(path),'touch_longest_structural_path':path}
        rows.append({'slot':slot,'ff':ff,'cones':cone})
    return {'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'cells_parsed':len(cells),'timestamps':rows,
            'original_i_touch_port_present':bool(re.search(r'input\s+i_touch\s*[,\n]',t)),
            'note':'Structural LUT fan-in paths within the synthesized cache module only. Synthesis can absorb touch logic into other hierarchy and import renamed shared nets; null is not absence of end-to-end touch dependence. INIT sensitivity/delay/routing and actual STA determine timing; no functional or timing PASS inferred.'}
roots={'P1':R.parent/'AB_P1缓存实施_20261024','P3':R}
out={k:parse(v/'physical/host_seed2/synthesize/hdmi_ddr_ov5640_top_syn.vm') for k,v in roots.items()}
(R/'results/timestamp_cone_comparison.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
for name,item in out.items():
    print(name,'cells',item['cells_parsed'])
    for row in item['timestamps']:print('slot',row['slot'],{p:c['touch_lut_depth'] for p,c in row['cones'].items()})

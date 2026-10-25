"""Count cache-local primitive pin loads, with the same parser for P4 and P7."""
from pathlib import Path
import re,collections,hashlib
TOKEN=re.compile(r'\\[^\s,{}]+(?:\s+\[\d+\])?|[A-Za-z_$][\w$]*(?:\[\d+\])*')
CONST=re.compile(r"\d+'[bhd][0-9a-fxz]+",re.I)
def measure(path):
    text=path.read_text();a=text.index('\nmodule undistort_cache_ab\n');b=text.index('\nendmodule',a);text=text[a:b]
    starts=list(re.finditer(r'^    (GTP_\w+)\s+/\*\s*(.*?)\s*\*/',text,re.M))
    cells=[];loads=collections.Counter();read_loads=collections.Counter();tag_banks=collections.Counter()
    for i,m in enumerate(starts):
        block=text[m.start():starts[i+1].start() if i+1<len(starts) else len(text)]
        ports={p:v.strip() for p,v in re.findall(r'\.(\w+)\s+\(([^()]*)\)',block)}
        c=dict(type=m[1],name=m[2].strip('\\ '),ports=ports);cells.append(c)
        for pin,expr in ports.items():
            if pin in ('Q','QN','DO','SPO','DPO','Z','Z0','Z1','O','F','S','CO','COUT','SUM','Y'):continue
            for net in TOKEN.findall(CONST.sub('',expr)):loads[re.sub(r'\s+','',net.lstrip('\\'))]+=1
        if c['type'].startswith('GTP_RAM') and ('tags' in c['name'] or c['name'].startswith(('tag_row','tag_seg'))):
            bank=re.search(r'tag_bank\[(\d+)\]',c['name'])
            if bank:tag_banks[int(bank[1])]+=1
            for net in TOKEN.findall(CONST.sub('',ports.get('RADDR',''))):read_loads[re.sub(r'\s+','',net.lstrip('\\'))]+=1
    tag_cells=[c for c in cells if c['type'].startswith('GTP_RAM') and ('tags' in c['name'] or c['name'].startswith(('tag_row','tag_seg')))]
    tag_ff=[c['name'] for c in cells if c['type'].startswith('GTP_DFF') and ('tags[' in c['name'] or c['name'].startswith(('tag_row[','tag_seg[')))]
    aliases={}
    for label,keys in [('qa[0]',(0,1)),('qb[0]',(2,3))]:
        names=[n for n in loads if n==label or any(re.fullmatch(r'tag_bank\[\d+\]\.key\['+str(k)+r'\]\.row_key\[0\]',n) for k in keys)]
        aliases[label]=dict(names=names,total_pin_loads=sum(loads[n] for n in names))
    return dict(netlist=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        tag_ram_primitives=len(tag_cells),tag_ram_types=dict(collections.Counter(c['type'] for c in tag_cells)),
        bank_ram_primitive_counts={str(k):v for k,v in sorted(tag_banks.items())},tag_ff=tag_ff,
        parity_pin_loads={n:aliases[n]['total_pin_loads'] for n in ('qa[0]','qb[0]')},parity_aliases=aliases,
        chosen_pin_loads={f'chosen[{i}]':loads[f'chosen[{i}]'] for i in range(8)},
        max_tag_ram_read_address_load=max(read_loads.values(),default=0),
        top_tag_ram_read_address_loads=read_loads.most_common(12),
        limitations='Cache module only; primitive pin counts, not routed fanout/STA. Same parser applied to both versions.')

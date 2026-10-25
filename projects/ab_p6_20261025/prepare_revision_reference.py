"""P6 implementation correction: retain local blocks, expose constant propagation."""
from pathlib import Path
import shutil,json,hashlib,re
W=Path(__file__).resolve().parent
B=W/'AB_P6标签RAM与局部替换_20261025'
R=W/'AB_P6R1局部块常量传播_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not (R/'candidate_identity.json').exists();R.mkdir(exist_ok=True)
for n in ('candidate','baseline','tests','prior_p1'):
    shutil.copytree(B/n,R/n,dirs_exist_ok=True)
P=R/'physical/host_seed2';P.mkdir(parents=True,exist_ok=True)
ident=json.loads((B/'physical/input_identity.json').read_text(encoding='utf-8'))
for row in ident['inputs']:
    p=B/'physical/host_seed2'/row['file'];assert sha(p)==row['sha256']
    q=P/row['file'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
shutil.copy2(B/'physical/host_seed2/synthesis_only.tcl',P/'synthesis_only.tcl')
src=(B/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
helper_start=src.index('// Age storage and its consumers share a local module.')
body=src[src.index('    reg [21:0] age[0:15];',helper_start):src.rindex('endmodule')]
body=body.replace('    generate for(view=0;','    for(view=0;').replace('    end endgenerate','    end')
start=src.index('        undistort_age_victim_group_p6 #(')
end=src.index('));',start)+3
instance=src[start:end]
connections=re.findall(r'\.(\w+)\(([^()]*)\)',instance)
connections=[(a,b) for a,b in connections if a!='GROUP']
assert len(connections)==25,len(connections)
widths={'i_mark_id':8,'i_alloc_id':8,'i_seq':22,'i_tag_valid':16,'i_tag_pending':16,
        'i_qfound':4,'i_qids':32,'o_ages':352,'o_mask':16,'o_leaf':248,'o_winner':31}
aliases=[]
for name,expr in connections:
    if name==expr:continue
    width=widths.get(name,1)
    decl='            wire '+(f'[{width-1}:0] ' if width>1 else '')+name
    aliases.append(decl+('= '+expr+';' if not name.startswith('o_') else ';\n            assign '+expr+'='+name+';'))
block='''        // P6R1: a lexical local block preserves all 22 bits while allowing
        // the existing host's constant sequence MSB to propagate in synthesis.
        begin:u_age_victim
            localparam integer GROUP=local_g;
'''+ '\n'.join(aliases)+'\n'+body+'        end\n'
src=src[:start]+block+src[end:helper_start]
assert src.count('module ')==1
for q in (R/'candidate/source/rtl/undistort_cache_ab.v',P/'source/rtl/undistort_cache_ab.v'):
    q.write_text(src,encoding='utf-8',newline='\n')
for n in ('run_equivalence.py','run_negative_checks.py','run_synthesis_gate.py',
          'compare_regression.py','inspect_physical.py','compare_warnings.py','process_snapshot.py'):
    text=(B/n).read_text(encoding='utf-8')
    text=text.replace(sha(B/'candidate/source/rtl/undistort_cache_ab.v'),sha(R/'candidate/source/rtl/undistort_cache_ab.v'))
    (R/n).write_text(text,encoding='utf-8')
rows=[]
for p in sorted((R/'candidate').rglob('*')):
    if p.is_file():
        old=W/'AB_P4缓存实施_20261024/candidate'/p.relative_to(R/'candidate')
        rows.append(dict(file=p.relative_to(R/'candidate').as_posix(),sha256=sha(p),baseline_sha256=sha(old)))
assert [x['file'] for x in rows if x['sha256']!=x['baseline_sha256']]==['source/rtl/undistort_cache_ab.v']
(R/'candidate_identity.json').write_text(json.dumps(dict(files=rows),indent=2),encoding='utf-8')
for row in ident['inputs']:row['sha256']=sha(P/row['file'])
ident['scope']='P6R1 lexical local blocks; no module boundary blocking constant propagation; full 22-bit age semantics retained'
(R/'physical/input_identity.json').write_text(json.dumps(ident,indent=2),encoding='utf-8')
assert sha(R/'candidate/source/rtl/undistort_core.v')=='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
note='''# P6R1：P6内部实现修正，尚未通过

P6首版标签RAM和逻辑LUT门槛通过，但FF8568超过P4的102%门槛（8433.36）。不进入PNR，不放宽门槛。

综合网表逐寄存器核对：P4年龄4032、leaf2113、winner年龄252；P6年龄4224、leaf2209、winner年龄264。增量192+96+12=300，恰为子模块隔离后无法利用宿主qseq最高位常量的开销。不是新增流水拍。

R1把子模块转为原地命名generate块，年龄、done mask、leaf和局部8选1树仍在同一局部块，保持原层次回读名称。完整22位声明、写入和比较保留，不截位、不限制输入；core、接口、状态与输出周期、125MHz、seed2、FDC/IP均不变。

原P6首版与所有结果保留在相邻AB_P6目录。R1先重跑5组逐拍、11种故障注入和同一资源门槛，只有全部通过才进入完整矩阵/物理验证。未有R1全帧、时序、位流或板级结论。
'''
(R/'README_当前进度.md').write_text(note,encoding='utf-8')
print(json.dumps(dict(root=str(R),cache_sha256=sha(R/'candidate/source/rtl/undistort_cache_ab.v')),ensure_ascii=False,indent=2))

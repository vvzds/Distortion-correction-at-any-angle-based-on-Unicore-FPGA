"""P7: twelve dynamically addressed packed tag banks; preserve P4 replacement."""
from pathlib import Path
import shutil,json,hashlib,re
W=Path(__file__).resolve().parent;B=W/'AB_P4缓存实施_20261024';R6=W/'AB_P6R1局部块常量传播_20261025'
R=W/'AB_P7标签RAM分银行_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not R.exists();R.mkdir()
for n in ('candidate','baseline','tests','prior_p1'):shutil.copytree(B/n,R/n)
P=R/'physical/host_seed2';P.mkdir(parents=True)
ident=json.loads((R6/'physical/input_identity.json').read_text(encoding='utf-8'))
for row in ident['inputs']:
    p=R6/'physical/host_seed2'/row['file'];assert sha(p)==row['sha256']
    q=P/row['file'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
src=(B/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
def change(a,b):
    global src
    assert src.count(a)==1,(a[:80],src.count(a));src=src.replace(a,b)
change('reg [10:0] tag_row[0:191];','wire [10:0] tag_row[0:191];')
change('reg [4:0] tag_seg[0:191];','wire [4:0] tag_seg[0:191];')
change('assign o_fetch_row=tag_row[o_fetch_bank];','assign o_fetch_row=bank_fetch[o_fetch_bank[7:4]][15:5];')
change('assign o_fetch_seg=tag_seg[o_fetch_bank];','assign o_fetch_seg=bank_fetch[o_fetch_bank[7:4]][4:0];')
change('                            tag_row[chosen]<=missing_row;tag_seg[chosen]<=missing_seg;\n','')
start=src.index('                        for(k=0;k<4;k=k+1)begin',src.index('                    Q_MATCH:begin'))
end=src.index('                        qstate<=Q_SELECT;',start)
old=src[start:end]
src=src[:start]+'''                        for(k=0;k<4;k=k+1)begin
                            for(g=0;g<12;g=g+1)begin
                                match_hit[k][g]<=bank_hit[k*12+g];
                                match_id[k*12+g]<=bank_id[k*12+g];
                            end
                        end
'''+src[end:]
anchor='    integer i,k,g,j,idx,sel,l,lu;'
new='''    // P7: local RAM address space is 16 slots, never 192-way global RAM.
    // Each physical bank keeps a dynamic write port and all 16 tag bits.
    wire [15:0] bank_fetch[0:11];
    wire [47:0] bank_hit;
    wire [7:0] bank_id[0:47];
    genvar tag_g,tag_v;
    generate for(tag_g=0;tag_g<12;tag_g=tag_g+1)begin:tag_bank
        reg [15:0] tags[0:15];
        assign bank_fetch[tag_g]=tags[o_fetch_bank[3:0]];
        for(tag_v=0;tag_v<16;tag_v=tag_v+1)begin:flat_view
            assign tag_row[16*tag_g+tag_v]=tags[tag_v][15:5];
            assign tag_seg[16*tag_g+tag_v]=tags[tag_v][4:0];
        end
        always @(posedge clk)begin
            if(rst_n && !i_frame_clear && alloc && chosen[7:4]==tag_g)
                tags[chosen[3:0]]<={missing_row,missing_seg};
        end
        genvar tag_k;
        for(tag_k=0;tag_k<4;tag_k=tag_k+1)begin:key
            wire [10:0] row_key=tag_k>=2?qb:qa;
            wire [4:0] seg_key=(tag_k%2)?qs1:qs0;
            reg hit;
            reg [7:0] id;
            integer slot_idx;
            always @*begin
                hit=0;id=0;
                for(slot_idx=0;slot_idx<8;slot_idx=slot_idx+1)begin
                    if(tag_valid[16*tag_g+2*slot_idx+row_key[0]] &&
                       tags[2*slot_idx+row_key[0]]=={row_key,seg_key})begin
                        hit=1;id=16*tag_g+2*slot_idx+row_key[0];
                    end
                end
            end
            assign bank_hit[tag_k*12+tag_g]=hit;
            assign bank_id[tag_k*12+tag_g]=id;
        end
    end endgenerate
'''
change(anchor,new+anchor)
for p in (R/'candidate/source/rtl/undistort_cache_ab.v',P/'source/rtl/undistort_cache_ab.v'):p.write_text(src,encoding='utf-8',newline='\n')
# Keep all original checks; only update the tag fixture's initialization backdoor.
t=R/'tests/cache_p4_equivalence_tb.sv';s=t.read_text(encoding='utf-8')
old='    dut.tag_row[id]=row;ref_dut.tag_row[id]=row;\n    dut.tag_seg[id]=seg;ref_dut.tag_seg[id]=seg;'
assert s.count(old)==1
lines=['    case(id[7:4])']+[f"        4'd{g}:dut.tag_bank[{g}].tags[id[3:0]]={{row[10:0],seg[4:0]}};" for g in range(12)]
lines+=['        default:$fatal(1,"Invalid tag seed ID");','    endcase','    ref_dut.tag_row[id]=row;ref_dut.tag_seg[id]=seg;']
s=s.replace(old,'\n'.join(lines)).replace('cache_p4_equivalence_tb','cache_p7_equivalence_tb').replace('P4_EQUIVALENCE','P7_EQUIVALENCE')
anchor='    for(cmp_i=0;cmp_i<256;cmp_i=cmp_i+1)';assert anchor in s
s=s.replace(anchor,'''    for(cmp_i=0;cmp_i<96;cmp_i=cmp_i+1)
        if(dut.victim_leaf[cmp_i]!==ref_dut.victim_leaf[cmp_i])$fatal(1,"victim leaf mismatch slot=%0d",cmp_i);
    for(cmp_i=0;cmp_i<12;cmp_i=cmp_i+1)
        if(dut.victim_hit[cmp_i]!==ref_dut.victim_hit[cmp_i] || dut.victim_age[cmp_i]!==ref_dut.victim_age[cmp_i] || dut.victim_id[cmp_i]!==ref_dut.victim_id[cmp_i])$fatal(1,"victim group mismatch group=%0d",cmp_i);
'''+anchor)
t.unlink();(R/'tests/cache_p7_equivalence_tb.sv').write_text(s,encoding='utf-8')
for n in ('run_equivalence.py','compare_regression.py'):
    s=(B/n).read_text(encoding='utf-8').replace('equivalence_p4','equivalence_p7').replace('regression_p4','regression_p7').replace('cache_p4_equivalence_tb','cache_p7_equivalence_tb').replace('P4_EQUIVALENCE','P7_EQUIVALENCE')
    s=s.replace(sha(B/'candidate/source/rtl/undistort_cache_ab.v'),sha(R/'candidate/source/rtl/undistort_cache_ab.v'))
    (R/n).write_text(s,encoding='utf-8')
for n in ('process_snapshot.py','inspect_physical.py','compare_warnings.py'):shutil.copy2(R6/n,R/n)
driver=(P/'analysis.tcl').read_text(encoding='utf-8')
(P/'synthesis_only.tcl').write_text(driver[:driver.index('\npnr ')].rstrip()+'\nexit\n',encoding='utf-8')
rows=[]
for p in sorted((R/'candidate').rglob('*')):
    if p.is_file():rows.append(dict(file=p.relative_to(R/'candidate').as_posix(),sha256=sha(p),baseline_sha256=sha(B/'candidate'/p.relative_to(R/'candidate'))))
assert [x['file'] for x in rows if x['sha256']!=x['baseline_sha256']]==['source/rtl/undistort_cache_ab.v']
(R/'candidate_identity.json').write_text(json.dumps(dict(files=rows),indent=2),encoding='utf-8')
for row in ident['inputs']:row['sha256']=sha(P/row['file'])
ident['scope']='P7 packed tags in 12 dynamically addressed RAM banks; P4 ages/replacement/FSM retained'
(R/'physical/input_identity.json').write_text(json.dumps(ident,indent=2),encoding='utf-8')
assert sha(R/'candidate/source/rtl/undistort_core.v')=='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
shutil.copy2(W/'AB_标签读取比较诊断_20261025/诊断结论与实施依据.md',R/'P7设计与筛选口径.md')
(R/'README_当前进度.md').write_text('# P7标签RAM银行候选，尚未通过\n\n先五组逐拍、定向标签写读/重复命中/优先级与负例，再综合资源与引脚负载筛选；通过才进入完整帧与固定125MHz/seed2 PNR。详见P7设计与筛选口径.md。\n',encoding='utf-8')
print(json.dumps(dict(root=str(R),cache_sha256=sha(R/'candidate/source/rtl/undistort_cache_ab.v')),ensure_ascii=False,indent=2))

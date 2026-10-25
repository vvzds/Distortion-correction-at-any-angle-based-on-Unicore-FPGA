"""Preserve P4 tag RAM; localize age storage, eligibility and group tournament."""
from pathlib import Path
import shutil,re,json,hashlib
W=Path(__file__).resolve().parent;B=W/'AB_P4缓存实施_20261024';P5=W/'AB_P5缓存分组结构_20261025';R=W/'AB_P6标签RAM与局部替换_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not R.exists();R.mkdir()
for name in ('candidate','baseline','tests','prior_p1'):shutil.copytree(B/name,R/name)
P=R/'physical/host_seed2';P.mkdir(parents=True)
identity=json.loads((P5/'physical/input_identity.json').read_text(encoding='utf-8'))
for row in identity['inputs']:
    p=P5/'physical/host_seed2'/row['file'];assert sha(p)==row['sha256']
    q=P/row['file'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
src=(B/'candidate/source/rtl/undistort_cache_ab.v').read_text(encoding='utf-8')
original=src
def change(a,b,n=1):
    global src
    assert src.count(a)==n,(a[:70],src.count(a),n)
    src=src.replace(a,b)
for a,b in [('reg [21:0] last_use[0:191];','wire [21:0] last_use[0:191];'),('reg [191:0] done_mask;','wire [191:0] done_mask;'),
            ('reg [11:0] victim_hit;','wire [11:0] victim_hit;'),('reg [7:0] victim_id[0:11];','wire [7:0] victim_id[0:11];'),
            ('reg [21:0] victim_age[0:11];','wire [21:0] victim_age[0:11];'),('reg [30:0] victim_leaf[0:95];','wire [30:0] victim_leaf[0:95];')]:change(a,b)
change('chosen<=0;chosen_ok<=0;done_mask<=0;','chosen<=0;chosen_ok<=0;')
change('qstate<=Q_IDLE;done_mask<=0;','qstate<=Q_IDLE;')
start=src.index('                // Each timestamp has one static writer.');end=src.index('                case(qstate)',start)
src=src[:start]+src[end:]
change('                        done_mask<=0;\n','')
start=src.index('                        case(qwhich)',src.index('                    Q_CHECK:begin'));end=src.index('                        endcase',start)+len('                        endcase')
selection=src[start:end];src=src[:start]+'                        found=local_check_found;sel=local_check_id;'+src[end:]
change("                            done_mask[sel]<=1'b1;\n",'');change("                            done_mask[chosen]<=1'b1;\n",'')
start=src.index('                    Q_ELIG:begin');end=src.index('                    Q_VICTIM:begin',start)
src=src[:start]+'''                    // P6: the same two stages are owned by local groups.
                    Q_ELIG:qstate<=Q_GROUP;
                    Q_GROUP:qstate<=Q_VICTIM;
'''+src[end:]
selection=re.sub(r'\bfound\b','local_check_found',selection);selection=re.sub(r'\bsel\b','local_check_id',selection)
top='''    // Tag arrays and writes stay in the original process to preserve RAM inference.
    reg local_check_found;
    reg [7:0] local_check_id;
    always @* begin
        local_check_found=1'bx;local_check_id=8'hxx;
SELECTION
    end
    genvar local_g,local_j;
    generate for(local_g=0;local_g<12;local_g=local_g+1)begin:local_group
        wire [351:0] group_ages;
        wire [15:0] group_mask;
        wire [247:0] group_leaf;
        wire [30:0] group_winner;
        undistort_age_victim_group_p6 #(.GROUP(local_g)) u_age_victim(
            .clk(clk),.rst_n(rst_n),.i_frame_clear(i_frame_clear),
            .i_select(qstate==Q_SELECT),.i_mark(qstate==Q_CHECK && local_check_found),.i_mark_id(local_check_id),
            .i_alloc(alloc),.i_alloc_id(chosen),.i_commit(qstate==Q_DONE),.i_seq(qseq),
            .i_touch(i_touch),.i_touch_ids(i_touch_ids),.i_touch_seq(i_touch_seq),
            .i_elig(qstate==Q_ELIG),.i_group(qstate==Q_GROUP),.i_parity(missing_row[0]),
            .i_tag_valid(tag_valid[16*local_g+:16]),.i_tag_pending(tag_pending[16*local_g+:16]),
            .i_retired_count(i_retired_count),.i_qfound(qfound),.i_qids({qid[3],qid[2],qid[1],qid[0]}),
            .o_ages(group_ages),.o_mask(group_mask),.o_leaf(group_leaf),.o_winner(group_winner));
        assign victim_hit[local_g]=group_winner[30];
        assign victim_age[local_g]=group_winner[29:8];assign victim_id[local_g]=group_winner[7:0];
        for(local_j=0;local_j<16;local_j=local_j+1)begin:age_view
            assign last_use[16*local_g+local_j]=group_ages[22*local_j+:22];
            assign done_mask[16*local_g+local_j]=group_mask[local_j];
        end
        for(local_j=0;local_j<8;local_j=local_j+1)begin:leaf_view
            assign victim_leaf[8*local_g+local_j]=group_leaf[31*local_j+:31];
        end
    end endgenerate
'''.replace('SELECTION',selection)
change('    integer i,k,g,j,idx,sel,l,lu;',top+'    integer i,k,g,j,idx,sel,l;')
helper='''
// Age storage and its consumers share a local module. No tag RAM is split.
module undistort_age_victim_group_p6 #(parameter integer GROUP=0)(
    input wire clk,rst_n,i_frame_clear,i_select,i_mark,
    input wire [7:0] i_mark_id,input wire i_alloc,input wire [7:0] i_alloc_id,
    input wire i_commit,input wire [21:0] i_seq,
    input wire i_touch,input wire [31:0] i_touch_ids,input wire [21:0] i_touch_seq,
    input wire i_elig,i_group,i_parity,
    input wire [15:0] i_tag_valid,i_tag_pending,input wire [21:0] i_retired_count,
    input wire [3:0] i_qfound,input wire [31:0] i_qids,
    output wire [351:0] o_ages,output wire [15:0] o_mask,
    output wire [247:0] o_leaf,output wire [30:0] o_winner
);
    reg [21:0] age[0:15];reg [15:0] mask;
    reg [30:0] leaf[0:7];reg [30:0] winner;
    wire bank_alloc=i_alloc && i_alloc_id[7:4]==GROUP;
    wire bank_mark=i_mark && i_mark_id[7:4]==GROUP;
    wire touch0=i_touch && i_touch_ids[7:4]==GROUP;
    wire touch1=i_touch && i_touch_ids[15:12]==GROUP;
    wire touch2=i_touch && i_touch_ids[23:20]==GROUP;
    wire touch3=i_touch && i_touch_ids[31:28]==GROUP;
    assign o_mask=mask;assign o_winner=winner;
    genvar view;
    generate for(view=0;view<16;view=view+1)begin:age_output
        assign o_ages[22*view+:22]=age[view];
    end
    for(view=0;view<8;view=view+1)begin:leaf_output
        assign o_leaf[31*view+:31]=leaf[view];
    end endgenerate
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)mask<=0;
        else if(i_frame_clear)mask<=0;
        else if(i_select)mask<=0;
        else if(bank_mark)mask[i_mark_id[3:0]]<=1'b1;
        else if(bank_alloc)mask[i_alloc_id[3:0]]<=1'b1;
    end
    integer s;
    // Same old-value semantics and priority. No reset/clear value is introduced.
    always @(posedge clk)begin
        if(!rst_n)begin end
        else if(i_frame_clear)begin end
        else for(s=0;s<16;s=s+1)begin
            if((bank_alloc && i_alloc_id[3:0]==s) || (i_commit && mask[s]))age[s]<=i_seq;
            else if((touch0 && i_touch_ids[3:0]==s) || (touch1 && i_touch_ids[11:8]==s) ||
                    (touch2 && i_touch_ids[19:16]==s) || (touch3 && i_touch_ids[27:24]==s))age[s]<=i_touch_seq;
        end
    end
    function [30:0] local_older;
        input [30:0] a,b;
        begin
            if(!a[30])local_older=b;
            else if(!b[30])local_older=a;
            else local_older=(a[29:8]<b[29:8])?a:b;
        end
    endfunction
    integer j,k,local_idx,gid;
    reg protected_id;
    reg [30:0] tree[0:15];
    always @(posedge clk)begin
        if(!rst_n)begin end
        else if(i_frame_clear)begin end
        else begin
            if(i_elig)begin
                for(j=0;j<8;j=j+1)begin
                    local_idx=2*j+i_parity;gid=16*GROUP+local_idx;protected_id=0;
                    for(k=0;k<4;k=k+1)
                        if(i_qfound[k] && i_qids[k*8+:8]==gid)protected_id=1;
                    leaf[j]<={(!protected_id && (!i_tag_valid[local_idx] ||
                        (!i_tag_pending[local_idx] && age[local_idx]<i_retired_count))),
                        (i_tag_valid[local_idx]?age[local_idx]:22'd0),gid[7:0]};
                end
            end
            if(i_group)begin
                for(j=0;j<8;j=j+1)tree[8+j]=leaf[j];
                for(j=7;j>0;j=j-1)tree[j]=local_older(tree[j*2],tree[j*2+1]);
                winner<=tree[1];
            end
        end
    end
endmodule
'''
src+=helper
for q in (R/'candidate/source/rtl/undistort_cache_ab.v',P/'source/rtl/undistort_cache_ab.v'):q.write_text(src,encoding='utf-8',newline='\n')
assert 'reg [10:0] tag_row[0:191];' in src and 'tag_row[chosen]<=missing_row;tag_seg[chosen]<=missing_seg;' in src
# Change only the timestamp seed backdoor; tag seeds and every original monitor stay.
t=R/'tests/cache_p4_equivalence_tb.sv';body=t.read_text(encoding='utf-8')
seed='    dut.last_use[id]=age;ref_dut.last_use[id]=age;';assert seed in body
cases=['    case(id[7:4])']
for group in range(12):cases.append(f"        4'd{group}:dut.local_group[{group}].u_age_victim.age[id[3:0]]=age;")
cases+=['        default:$fatal(1,"Invalid timestamp seed ID");','    endcase','    ref_dut.last_use[id]=age;']
body=body.replace(seed,'\n'.join(cases)).replace('cache_p4_equivalence_tb','cache_p6_equivalence_tb').replace('P4_EQUIVALENCE','P6_EQUIVALENCE')
anchor='    for(cmp_i=0;cmp_i<256;cmp_i=cmp_i+1)';assert anchor in body
extra='''    for(cmp_i=0;cmp_i<96;cmp_i=cmp_i+1)
        if(dut.victim_leaf[cmp_i]!==ref_dut.victim_leaf[cmp_i])$fatal(1,"victim leaf mismatch slot=%0d",cmp_i);
    for(cmp_i=0;cmp_i<12;cmp_i=cmp_i+1)
        if(dut.victim_hit[cmp_i]!==ref_dut.victim_hit[cmp_i] || dut.victim_age[cmp_i]!==ref_dut.victim_age[cmp_i] || dut.victim_id[cmp_i]!==ref_dut.victim_id[cmp_i])$fatal(1,"victim group mismatch group=%0d",cmp_i);
'''
body=body.replace(anchor,extra+anchor);t.unlink();(R/'tests/cache_p6_equivalence_tb.sv').write_text(body,encoding='utf-8')
runner=(B/'run_equivalence.py').read_text(encoding='utf-8').replace('equivalence_p4','equivalence_p6').replace('cache_p4_equivalence_tb','cache_p6_equivalence_tb').replace('P4_EQUIVALENCE','P6_EQUIVALENCE')
(R/'run_equivalence.py').write_text(runner,encoding='utf-8')
for name in ('process_snapshot.py','inspect_physical.py','compare_warnings.py'):
    shutil.copy2(P5/name,R/name)
run=(B/'compare_regression.py').read_text(encoding='utf-8').replace('regression_p4','regression_p6').replace('425ea5c734c174d0e4e08619d4ed8aebf96e95f60e8a60df9b2fcc010341fb49',sha(R/'candidate/source/rtl/undistort_cache_ab.v'))
(R/'compare_regression.py').write_text(run,encoding='utf-8')
rows=[]
for p in sorted((R/'candidate').rglob('*')):
    if p.is_file():rows.append(dict(file=p.relative_to(R/'candidate').as_posix(),sha256=sha(p),baseline_sha256=sha(B/'candidate'/p.relative_to(R/'candidate'))))
assert [x['file'] for x in rows if x['sha256']!=x['baseline_sha256']]==['source/rtl/undistort_cache_ab.v']
(R/'candidate_identity.json').write_text(json.dumps(dict(files=rows),indent=2),encoding='utf-8')
for row in identity['inputs']:row['sha256']=sha(P/row['file'])
identity['scope']='P6 age/eligibility/group tournament localized; P4 tag RAM and all other inputs retained; single unrestricted timing driver'
(R/'physical/input_identity.json').write_text(json.dumps(identity,indent=2),encoding='utf-8')
driver=(P/'analysis.tcl').read_text(encoding='utf-8')
(P/'synthesis_only.tcl').write_text(driver[:driver.index('\npnr ')].rstrip()+'\nexit\n',encoding='utf-8')
(R/'README_当前进度.md').write_text('''# P6实现中，尚未通过

用户批准结束P5并寻找其他方法。P6保留P4的tag_row/tag_seg声明、读写及RAM推断形式；把年龄存储、mask、eligible计算与组内8选1替换树一起移入12个16槽局部模块，沿用原Q_ELIG/Q_GROUP拍，保持原12选1全局树。core/map/接口及输出周期不变，没有位流。

先跑逐拍（增加96项leaf及12组winner对照）和故障注入，再做综合资源筛选。只有标签RAM保留且FF/逻辑代价可接受时才进入完整帧/物理长验证；若本方法证据不好，先向用户说明并询问是否继续换方法。
''',encoding='utf-8')
assert sha(R/'candidate/source/rtl/undistort_core.v')=='9ba7d1e4ac65a2063b89c5e5a57766b20d84d3f8eb53d0556cc88317d3efff68'
print(json.dumps(dict(root=str(R),cache_sha256=sha(R/'candidate/source/rtl/undistort_cache_ab.v'),candidate_inputs=len(rows),physical_inputs=len(identity['inputs'])),ensure_ascii=False,indent=2))

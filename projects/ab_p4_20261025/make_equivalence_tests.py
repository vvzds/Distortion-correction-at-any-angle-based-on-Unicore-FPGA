from pathlib import Path
import re
R=Path(__file__).resolve().parent
source=(R/'baseline/undistort_cache_ab.v').read_text(encoding='utf-8')
header=source.split(')(\n',1)[1].split('\n);',1)[0]
ports=[]
for direction,width,names in re.findall(r'(input|output)\s+(?:wire|reg)\s*(\[[^]]+\])?\s*([^\n]+)',header):
    for name in names.strip().rstrip(',').split(','):
        ports.append((direction,width,name.strip()))
def instance(module,name):
    return module+' '+name+'(\n'+',\n'.join('    .'+n+'('+ (n if d=='input' else '')+')' for d,w,n in ports)+'\n);\n'
monitor='''
integer compared_edges=0,completed=0,allocations=0,blocked_allocations=0;
integer done_touch=0,alloc_touch=0,elig_touch=0,cmp_i;
reg [191:0] expected_mask;
always @(posedge clk)begin
    if(rst_n && !i_frame_clear)begin
        if(dut.qstate==6)begin
            expected_mask=0;
            for(cmp_i=0;cmp_i<4;cmp_i=cmp_i+1)expected_mask[dut.qid[cmp_i]]=1;
            if(dut.done_mask!==expected_mask)$fatal(1,"MASK mismatch before DONE");
            completed=completed+1;
            if(i_touch)done_touch=done_touch+1;
        end
        if(dut.qstate==5)begin
            if(dut.chosen_ok)begin allocations=allocations+1;if(i_touch)alloc_touch=alloc_touch+1;end
            else blocked_allocations=blocked_allocations+1;
        end
        if(dut.qstate==7 && i_touch)elig_touch=elig_touch+1;
    end
    #1;
    compared_edges=compared_edges+1;
OUTPUT_CHECKS
STATE_CHECKS
    for(cmp_i=0;cmp_i<192;cmp_i=cmp_i+1)begin
        if(dut.last_use[cmp_i]!==ref_dut.last_use[cmp_i])$fatal(1,"last_use mismatch slot=%0d edge=%0d state=%0d",cmp_i,compared_edges,dut.qstate);
        if(dut.tag_row[cmp_i]!==ref_dut.tag_row[cmp_i] || dut.tag_seg[cmp_i]!==ref_dut.tag_seg[cmp_i])$fatal(1,"tag mismatch");
    end
    for(cmp_i=0;cmp_i<4;cmp_i=cmp_i+1)begin
        if(dut.qid[cmp_i]!==ref_dut.qid[cmp_i])$fatal(1,"qid mismatch");
    end
    for(cmp_i=0;cmp_i<256;cmp_i=cmp_i+1)
        if(dut.fetch_fifo[cmp_i]!==ref_dut.fetch_fifo[cmp_i])$fatal(1,"fetch FIFO mismatch");
    if((!rst_n || i_frame_clear) && dut.done_mask!==192'd0)$fatal(1,"MASK reset/clear failure");
end
'''
monitor=monitor.replace('OUTPUT_CHECKS','\n'.join('    if(dut.'+n+'!==ref_dut.'+n+')$fatal(1,"output '+n+' mismatch edge=%0d",compared_edges);' for d,w,n in ports if d=='output'))
states=['qstate','qa','qb','qs0','qs1','qseq','qfound','qwhich','chosen','chosen_ok','tag_valid','tag_ready','tag_pending','fetch_wr','fetch_rd','fetch_count','load_active','load_line','load_bank','load_row','load_beat','line_valid','first_pending','output_pending']
monitor=monitor.replace('STATE_CHECKS','\n'.join('    if(dut.'+n+'!==ref_dut.'+n+')$fatal(1,"state '+n+' mismatch");' for n in states))
body=r'''
integer j,n,s,timeout,allhit_cycles,tests=0;
reg [31:0] selected_ids;
task tick;begin @(posedge clk);#2;@(negedge clk);end endtask
task reset_both;begin
    rst_n=0;i_lookup_req=0;i_touch=0;i_frame_clear=0;i_line_mode=0;
    i_fetch_gnt=0;i_load_begin=0;i_load_vld=0;i_load_last=0;i_sample_req=0;
    repeat(2)tick;rst_n=1;tick;
end endtask
task slot;
input integer id,row,seg,age,pending;
begin
    dut.tag_valid[id]=1;ref_dut.tag_valid[id]=1;
    dut.tag_ready[id]=!pending;ref_dut.tag_ready[id]=!pending;
    dut.tag_pending[id]=pending;ref_dut.tag_pending[id]=pending;
    dut.tag_row[id]=row;ref_dut.tag_row[id]=row;
    dut.tag_seg[id]=seg;ref_dut.tag_seg[id]=seg;
    dut.last_use[id]=age;ref_dut.last_use[id]=age;
end endtask
task request;
input integer a,b,x,seq;
begin
    i_lookup_a=a;i_lookup_b=b;i_lookup_x=x;i_lookup_seq=seq;
    i_lookup_req=1;tick;i_lookup_req=0;
end endtask
task finish_lookup;begin
    timeout=0;
    while(!dut.o_lookup_done && timeout<1000)begin tick;timeout=timeout+1;end
    if(!dut.o_lookup_done)$fatal(1,"lookup timeout");
    selected_ids={dut.o_id_b1,dut.o_id_b0,dut.o_id_a1,dut.o_id_a0};
    tick;tests=tests+1;
end endtask
task reach;input integer state;begin
    timeout=0;
    while(dut.qstate!=state && timeout<300)begin tick;timeout=timeout+1;end
    if(dut.qstate!=state)$fatal(1,"state not reached %0d",state);
end endtask
initial begin
    @(negedge clk);
    reset_both;
    // F01: four distinct hits; no initial timestamp initialization outside fixtures.
    slot(0,20,0,1,0);slot(2,20,1,1,0);slot(1,21,0,1,0);slot(3,21,1,1,0);
    request(20,21,63,8);allhit_cycles=0;
    while(!dut.o_lookup_done)begin tick;allhit_cycles=allhit_cycles+1;end
    if(allhit_cycles!=7)$fatal(1,"all-hit lookup latency %0d",allhit_cycles);
    tests=tests+1;tick;
    // F02/F03: duplicate keys and clamp/segment boundaries, publicly allocated.
    reset_both;i_retired_count=22'h3fffff;
    request(0,0,0,9);finish_lookup;
    request(0,0,63,10);finish_lookup;
    request(2,3,64,11);finish_lookup;
    request(2,3,127,12);finish_lookup;
    request(2,3,128,13);finish_lookup;
    request(1078,1079,1918,14);finish_lookup;
    request(1078,1079,1919,15);finish_lookup;
    // F04/F08: last key allocates; allocation overrides simultaneous touch.
    reset_both;slot(0,20,0,1,0);slot(2,20,1,1,0);slot(1,21,0,1,0);
    request(20,21,63,17);reach(5);
    i_touch=1;i_touch_ids={8'd190,8'd190,dut.chosen,dut.chosen};i_touch_seq=22'h3fffff;
    tick;i_touch=0;finish_lookup;
    // F07: completion beats a higher touch seq; other slots still touched.
    request(20,21,63,18);reach(6);
    i_touch=1;i_touch_ids={8'd190,8'd190,dut.qid[0],dut.qid[0]};i_touch_seq=22'h3ffffe;
    tick;i_touch=0;finish_lookup;
    request(20,21,63,19);reach(6);
    i_touch=1;i_touch_ids={8'd189,dut.qid[1],dut.qid[2],dut.qid[3]};i_touch_seq=0;
    tick;i_touch=0;finish_lookup;
    // F05/F09: no eligible slots, including age==retired. Touch changes age
    // on ELIG but must not affect the snapshot until a subsequent retry.
    reset_both;i_retired_count=50;
    for(j=0;j<192;j=j+1)slot(j,100+j,j%30,50,0);
    request(2,3,63,100);reach(5);
    if(dut.chosen_ok)$fatal(1,"strict retirement threshold violated");
    tick;reach(7);i_touch=1;i_touch_ids={8'd0,8'd0,8'd0,8'd0};i_touch_seq=0;
    tick;i_touch=0;reach(5);
    if(dut.chosen_ok)$fatal(1,"ELIG incorrectly forwarded touch");
    tick;i_retired_count=22'h3fffff;finish_lookup;
    // F06: later selected hit must stay protected during earlier miss.
    reset_both;i_retired_count=100;
    for(j=0;j<192;j=j+1)slot(j,100+j,j%30,20,0);
    slot(20,20,1,0,0); // future key 1, attractive oldest victim
    request(20,21,63,90);reach(5);
    if(dut.chosen==20)$fatal(1,"future hit was evicted");
    finish_lookup;
    // F10: equal-age victim tree, then repeated requests exercise reuse.
    reset_both;i_retired_count=100;
    for(j=0;j<192;j=j+1)slot(j,100+j,j%30,1,0);
    request(4,5,63,2);finish_lookup;
    for(n=0;n<24;n=n+1)begin
        i_retired_count=22'h3fffff;
        request((n%20)*2,(n%20)*2+1,(n*63)%1920,100+n);finish_lookup;
    end
    // F11: clear and reset in every reachable lookup state, including DONE.
    for(s=0;s<=8;s=s+1)begin
        reset_both;
        if(s!=0)begin request(20,21,63,22);reach(s);end
        i_frame_clear=1;tick;i_frame_clear=0;tick;tests=tests+1;
        reset_both;
        if(s!=0)begin request(20,21,63,23);reach(s);end
        rst_n=0;tick;rst_n=1;tick;tests=tests+1;
    end
    // F13: full 22-bit sequence extremes and ignored out-of-range touch IDs.
    reset_both;i_retired_count=22'h3fffff;
    request(0,0,1919,22'h3fffff);finish_lookup;
    i_touch=1;i_touch_ids={8'd255,8'd192,8'd191,8'd0};i_touch_seq=22'h3fffff;tick;
    i_touch_seq=0;tick;i_touch=0;
    request(0,0,1919,0);finish_lookup;
    if(done_touch<2 || alloc_touch<1 || elig_touch<1 || blocked_allocations<2)$fatal(1,"missing collision coverage");
    $display("P4_EQUIVALENCE PASS tests=%0d edges=%0d done=%0d alloc=%0d blocked=%0d touch_done=%0d touch_alloc=%0d touch_elig=%0d allhit=%0d",tests,compared_edges,completed,allocations,blocked_allocations,done_touch,alloc_touch,elig_touch,allhit_cycles);
    $finish;
end
initial begin #2000000;$fatal(1,"watchdog");end
'''
decl='\n'.join('reg '+w+' '+n+'=0;' for d,w,n in ports if d=='input')
tb='`timescale 1ns/1ps\nmodule cache_p4_equivalence_tb;\n'+decl+'\nalways #4 clk=~clk;\n'+instance('undistort_cache_ab','dut')+instance('undistort_cache_ab_reference','ref_dut')+monitor+body+'\nendmodule\n'
(R/'tests').mkdir(exist_ok=True)
(R/'tests/cache_p4_equivalence_tb.sv').write_text(tb,encoding='utf-8')
# Reuse original black-box memory/load tests with an independent reference
# instance and per-edge exact comparisons; no change to their stimulus.
for name in ['cache72_ab_tb.v','segment_cache_tb.v','cache_mode_switch_tb.v','cache_boundary_r3_tb.v']:
    text=(R/'candidate/sim'/name).read_text(encoding='utf-8-sig')
    m=re.search(r'undistort_cache_ab\s+(?:#\(.*?\)\s*)?dut\s*\((.*?)\);',text,re.S)
    assert m,name
    inst=m.group(0).replace('undistort_cache_ab','undistort_cache_ab_reference',1).replace('dut(','ref_dut(',1).replace('dut (','ref_dut (',1)
    for d,w,n in ports:
        if d=='output':inst=re.sub(r'\.'+n+r'\([^)]*\)','.'+n+'()',inst)
    compare=monitor.replace('i_frame_clear','dut.i_frame_clear').replace('if(i_touch)','if(dut.i_touch)').replace('&& i_touch','&& dut.i_touch')
    # A different frame-clear signal name appears in each inherited TB.
    text=text[:m.end()]+'\n'+inst+'\n'+compare+text[m.end():]
    (R/'tests'/name).write_text(text,encoding='utf-8')
print('Generated directed dual-instance test and four unchanged-stimulus comparison harnesses.')

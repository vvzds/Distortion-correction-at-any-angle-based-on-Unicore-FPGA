`timescale 1ns/1ps
module cache_p7_banks_tb;
reg  clk=0;
reg  rst_n=0;
reg  i_frame_clear=0;
reg  i_line_mode=0;
reg  i_load_begin=0;
reg [7:0] i_load_bank=0;
reg [10:0] i_load_row=0;
reg  i_load_vld=0;
reg  i_load_last=0;
reg [255:0] i_load_data=0;
reg [10:0] i_query_row_a=0;
reg [10:0] i_query_row_b=0;
reg [10:0] i_prefetch_row=0;
reg  i_sample_req=0;
reg [7:0] i_sample_bank_a=0;
reg [7:0] i_sample_bank_b=0;
reg [7:0] i_sample_bank_a1=0;
reg [7:0] i_sample_bank_b1=0;
reg [10:0] i_sample_x=0;
reg  i_lookup_req=0;
reg [10:0] i_lookup_a=0;
reg [10:0] i_lookup_b=0;
reg [10:0] i_lookup_x=0;
reg [21:0] i_lookup_seq=0;
reg  i_touch=0;
reg [31:0] i_touch_ids=0;
reg [21:0] i_touch_seq=0;
reg [21:0] i_retired_count=0;
reg [31:0] i_ready_ids=0;
reg  i_fetch_gnt=0;
always #4 clk=~clk;
undistort_cache_ab dut(
    .clk(clk),
    .rst_n(rst_n),
    .i_frame_clear(i_frame_clear),
    .i_line_mode(i_line_mode),
    .i_load_begin(i_load_begin),
    .i_load_bank(i_load_bank),
    .i_load_row(i_load_row),
    .i_load_vld(i_load_vld),
    .i_load_last(i_load_last),
    .i_load_data(i_load_data),
    .o_load_done(),
    .o_load_error(),
    .i_query_row_a(i_query_row_a),
    .i_query_row_b(i_query_row_b),
    .i_prefetch_row(i_prefetch_row),
    .o_hit_a(),
    .o_hit_b(),
    .o_prefetch_hit(),
    .o_bank_a(),
    .o_bank_b(),
    .i_sample_req(i_sample_req),
    .i_sample_bank_a(i_sample_bank_a),
    .i_sample_bank_b(i_sample_bank_b),
    .i_sample_bank_a1(i_sample_bank_a1),
    .i_sample_bank_b1(i_sample_bank_b1),
    .i_sample_x(i_sample_x),
    .o_sample_valid(),
    .o_p00(),
    .o_p01(),
    .o_p10(),
    .o_p11(),
    .i_lookup_req(i_lookup_req),
    .i_lookup_a(i_lookup_a),
    .i_lookup_b(i_lookup_b),
    .i_lookup_x(i_lookup_x),
    .i_lookup_seq(i_lookup_seq),
    .o_lookup_busy(),
    .o_lookup_done(),
    .o_id_a0(),
    .o_id_a1(),
    .o_id_b0(),
    .o_id_b1(),
    .i_touch(i_touch),
    .i_touch_ids(i_touch_ids),
    .i_touch_seq(i_touch_seq),
    .i_retired_count(i_retired_count),
    .i_ready_ids(i_ready_ids),
    .o_ids_ready(),
    .o_fetch_req(),
    .o_fetch_bank(),
    .o_fetch_row(),
    .o_fetch_seg(),
    .i_fetch_gnt(i_fetch_gnt)
);
undistort_cache_ab_reference ref_dut(
    .clk(clk),
    .rst_n(rst_n),
    .i_frame_clear(i_frame_clear),
    .i_line_mode(i_line_mode),
    .i_load_begin(i_load_begin),
    .i_load_bank(i_load_bank),
    .i_load_row(i_load_row),
    .i_load_vld(i_load_vld),
    .i_load_last(i_load_last),
    .i_load_data(i_load_data),
    .o_load_done(),
    .o_load_error(),
    .i_query_row_a(i_query_row_a),
    .i_query_row_b(i_query_row_b),
    .i_prefetch_row(i_prefetch_row),
    .o_hit_a(),
    .o_hit_b(),
    .o_prefetch_hit(),
    .o_bank_a(),
    .o_bank_b(),
    .i_sample_req(i_sample_req),
    .i_sample_bank_a(i_sample_bank_a),
    .i_sample_bank_b(i_sample_bank_b),
    .i_sample_bank_a1(i_sample_bank_a1),
    .i_sample_bank_b1(i_sample_bank_b1),
    .i_sample_x(i_sample_x),
    .o_sample_valid(),
    .o_p00(),
    .o_p01(),
    .o_p10(),
    .o_p11(),
    .i_lookup_req(i_lookup_req),
    .i_lookup_a(i_lookup_a),
    .i_lookup_b(i_lookup_b),
    .i_lookup_x(i_lookup_x),
    .i_lookup_seq(i_lookup_seq),
    .o_lookup_busy(),
    .o_lookup_done(),
    .o_id_a0(),
    .o_id_a1(),
    .o_id_b0(),
    .o_id_b1(),
    .i_touch(i_touch),
    .i_touch_ids(i_touch_ids),
    .i_touch_seq(i_touch_seq),
    .i_retired_count(i_retired_count),
    .i_ready_ids(i_ready_ids),
    .o_ids_ready(),
    .o_fetch_req(),
    .o_fetch_bank(),
    .o_fetch_row(),
    .o_fetch_seg(),
    .i_fetch_gnt(i_fetch_gnt)
);

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
    if(dut.o_load_done!==ref_dut.o_load_done)$fatal(1,"output o_load_done mismatch edge=%0d",compared_edges);
    if(dut.o_load_error!==ref_dut.o_load_error)$fatal(1,"output o_load_error mismatch edge=%0d",compared_edges);
    if(dut.o_hit_a!==ref_dut.o_hit_a)$fatal(1,"output o_hit_a mismatch edge=%0d",compared_edges);
    if(dut.o_hit_b!==ref_dut.o_hit_b)$fatal(1,"output o_hit_b mismatch edge=%0d",compared_edges);
    if(dut.o_prefetch_hit!==ref_dut.o_prefetch_hit)$fatal(1,"output o_prefetch_hit mismatch edge=%0d",compared_edges);
    if(dut.o_bank_a!==ref_dut.o_bank_a)$fatal(1,"output o_bank_a mismatch edge=%0d",compared_edges);
    if(dut.o_bank_b!==ref_dut.o_bank_b)$fatal(1,"output o_bank_b mismatch edge=%0d",compared_edges);
    if(dut.o_sample_valid!==ref_dut.o_sample_valid)$fatal(1,"output o_sample_valid mismatch edge=%0d",compared_edges);
    if(dut.o_p00!==ref_dut.o_p00)$fatal(1,"output o_p00 mismatch edge=%0d",compared_edges);
    if(dut.o_p01!==ref_dut.o_p01)$fatal(1,"output o_p01 mismatch edge=%0d",compared_edges);
    if(dut.o_p10!==ref_dut.o_p10)$fatal(1,"output o_p10 mismatch edge=%0d",compared_edges);
    if(dut.o_p11!==ref_dut.o_p11)$fatal(1,"output o_p11 mismatch edge=%0d",compared_edges);
    if(dut.o_lookup_busy!==ref_dut.o_lookup_busy)$fatal(1,"output o_lookup_busy mismatch edge=%0d",compared_edges);
    if(dut.o_lookup_done!==ref_dut.o_lookup_done)$fatal(1,"output o_lookup_done mismatch edge=%0d",compared_edges);
    if(dut.o_id_a0!==ref_dut.o_id_a0)$fatal(1,"output o_id_a0 mismatch edge=%0d",compared_edges);
    if(dut.o_id_a1!==ref_dut.o_id_a1)$fatal(1,"output o_id_a1 mismatch edge=%0d",compared_edges);
    if(dut.o_id_b0!==ref_dut.o_id_b0)$fatal(1,"output o_id_b0 mismatch edge=%0d",compared_edges);
    if(dut.o_id_b1!==ref_dut.o_id_b1)$fatal(1,"output o_id_b1 mismatch edge=%0d",compared_edges);
    if(dut.o_ids_ready!==ref_dut.o_ids_ready)$fatal(1,"output o_ids_ready mismatch edge=%0d",compared_edges);
    if(dut.o_fetch_req!==ref_dut.o_fetch_req)$fatal(1,"output o_fetch_req mismatch edge=%0d",compared_edges);
    if(dut.o_fetch_bank!==ref_dut.o_fetch_bank)$fatal(1,"output o_fetch_bank mismatch edge=%0d",compared_edges);
    if(dut.o_fetch_row!==ref_dut.o_fetch_row)$fatal(1,"output o_fetch_row mismatch edge=%0d",compared_edges);
    if(dut.o_fetch_seg!==ref_dut.o_fetch_seg)$fatal(1,"output o_fetch_seg mismatch edge=%0d",compared_edges);
    if(dut.qstate!==ref_dut.qstate)$fatal(1,"state qstate mismatch");
    if(dut.qa!==ref_dut.qa)$fatal(1,"state qa mismatch");
    if(dut.qb!==ref_dut.qb)$fatal(1,"state qb mismatch");
    if(dut.qs0!==ref_dut.qs0)$fatal(1,"state qs0 mismatch");
    if(dut.qs1!==ref_dut.qs1)$fatal(1,"state qs1 mismatch");
    if(dut.qseq!==ref_dut.qseq)$fatal(1,"state qseq mismatch");
    if(dut.qfound!==ref_dut.qfound)$fatal(1,"state qfound mismatch");
    if(dut.qwhich!==ref_dut.qwhich)$fatal(1,"state qwhich mismatch");
    if(dut.chosen!==ref_dut.chosen)$fatal(1,"state chosen mismatch");
    if(dut.chosen_ok!==ref_dut.chosen_ok)$fatal(1,"state chosen_ok mismatch");
    if(dut.tag_valid!==ref_dut.tag_valid)$fatal(1,"state tag_valid mismatch");
    if(dut.tag_ready!==ref_dut.tag_ready)$fatal(1,"state tag_ready mismatch");
    if(dut.tag_pending!==ref_dut.tag_pending)$fatal(1,"state tag_pending mismatch");
    if(dut.fetch_wr!==ref_dut.fetch_wr)$fatal(1,"state fetch_wr mismatch");
    if(dut.fetch_rd!==ref_dut.fetch_rd)$fatal(1,"state fetch_rd mismatch");
    if(dut.fetch_count!==ref_dut.fetch_count)$fatal(1,"state fetch_count mismatch");
    if(dut.load_active!==ref_dut.load_active)$fatal(1,"state load_active mismatch");
    if(dut.load_line!==ref_dut.load_line)$fatal(1,"state load_line mismatch");
    if(dut.load_bank!==ref_dut.load_bank)$fatal(1,"state load_bank mismatch");
    if(dut.load_row!==ref_dut.load_row)$fatal(1,"state load_row mismatch");
    if(dut.load_beat!==ref_dut.load_beat)$fatal(1,"state load_beat mismatch");
    if(dut.line_valid!==ref_dut.line_valid)$fatal(1,"state line_valid mismatch");
    if(dut.first_pending!==ref_dut.first_pending)$fatal(1,"state first_pending mismatch");
    if(dut.output_pending!==ref_dut.output_pending)$fatal(1,"state output_pending mismatch");
    for(cmp_i=0;cmp_i<192;cmp_i=cmp_i+1)begin
        if(dut.last_use[cmp_i]!==ref_dut.last_use[cmp_i])$fatal(1,"last_use mismatch slot=%0d edge=%0d state=%0d",cmp_i,compared_edges,dut.qstate);
        if(dut.tag_row[cmp_i]!==ref_dut.tag_row[cmp_i] || dut.tag_seg[cmp_i]!==ref_dut.tag_seg[cmp_i])$fatal(1,"tag mismatch");
    end
    for(cmp_i=0;cmp_i<4;cmp_i=cmp_i+1)begin
        if(dut.qid[cmp_i]!==ref_dut.qid[cmp_i])$fatal(1,"qid mismatch");
    end
    for(cmp_i=0;cmp_i<96;cmp_i=cmp_i+1)
        if(dut.victim_leaf[cmp_i]!==ref_dut.victim_leaf[cmp_i])$fatal(1,"victim leaf mismatch slot=%0d",cmp_i);
    for(cmp_i=0;cmp_i<12;cmp_i=cmp_i+1)
        if(dut.victim_hit[cmp_i]!==ref_dut.victim_hit[cmp_i] || dut.victim_age[cmp_i]!==ref_dut.victim_age[cmp_i] || dut.victim_id[cmp_i]!==ref_dut.victim_id[cmp_i])$fatal(1,"victim group mismatch group=%0d",cmp_i);
    for(cmp_i=0;cmp_i<256;cmp_i=cmp_i+1)
        if(dut.fetch_fifo[cmp_i]!==ref_dut.fetch_fifo[cmp_i])$fatal(1,"fetch FIFO mismatch");
    if((!rst_n || i_frame_clear) && dut.done_mask!==192'd0)$fatal(1,"MASK reset/clear failure");
end

integer j,n,s,timeout,allhit_cycles,tests=0;
reg [31:0] selected_ids;
reg [7:0] expected_slot;
reg [31:0] load_pattern;
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
    case(id[7:4])
        4'd0:dut.tag_bank[0].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd1:dut.tag_bank[1].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd2:dut.tag_bank[2].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd3:dut.tag_bank[3].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd4:dut.tag_bank[4].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd5:dut.tag_bank[5].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd6:dut.tag_bank[6].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd7:dut.tag_bank[7].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd8:dut.tag_bank[8].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd9:dut.tag_bank[9].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd10:dut.tag_bank[10].tags[id[3:0]]={row[10:0],seg[4:0]};
        4'd11:dut.tag_bank[11].tags[id[3:0]]={row[10:0],seg[4:0]};
        default:$fatal(1,"Invalid tag seed ID");
    endcase
    ref_dut.tag_row[id]=row;ref_dut.tag_seg[id]=seg;
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
    // P7B01: all 192 physical slots, including every bank/parity/address boundary.
    // Only the target is eligible; use the PUBLIC allocation/write/fetch path.
    for(n=0;n<192;n=n+1)begin
        reset_both;i_retired_count=22'h3fffff;
        for(j=0;j<192;j=j+1)slot(j,1300+j,j%30,1,1);
        slot(n,1300+n,n%30,0,0);
        request(((n*34)%1078)+(n%2),((n*34)%1078)+(n%2),(n%30)*64+4,1000+n);
        finish_lookup;
        if(selected_ids!=={4{n[7:0]}})$fatal(1,"bank allocation target=%0d actual=%h",n,selected_ids);
        if(!dut.o_fetch_req || dut.o_fetch_bank!==n[7:0] ||
           dut.o_fetch_row!==(((n*34)%1078)+(n%2)) || dut.o_fetch_seg!==(n%30))
            $fatal(1,"bank fetch decode target=%0d row=%0d seg=%0d",n,dut.o_fetch_row,dut.o_fetch_seg);
        i_fetch_gnt=1;tick;i_fetch_gnt=0;
        i_load_begin=1;i_load_bank=n;i_load_row=((n*34)%1078)+(n%2);tick;i_load_begin=0;
        for(j=0;j<4;j=j+1)begin
            load_pattern=32'h5a000000+n*4+j;
            i_load_vld=1;i_load_last=j==3;i_load_data={8{load_pattern}};tick;
        end
        i_load_vld=0;i_load_last=0;tick;
        i_ready_ids={4{n[7:0]}};#1;
        if(!dut.o_ids_ready)$fatal(1,"bank ready target=%0d",n);
        request(((n*34)%1078)+(n%2),((n*34)%1078)+(n%2),(n%30)*64+4,2000+n);
        finish_lookup;
        if(selected_ids!=={4{n[7:0]}})$fatal(1,"bank repeat hit target=%0d",n);
    end
    // P7B02: intentionally duplicate keys: largest slot and largest bank win.
    for(n=0;n<24;n=n+1)begin
        reset_both;
        for(j=0;j<8;j=j+1)slot(16*(n/2)+2*j+(n%2),20+(n%2),3,1,0);
        request(20+(n%2),20+(n%2),3*64+4,3000+n);finish_lookup;
        expected_slot=16*(n/2)+14+(n%2);
        if(selected_ids!=={4{expected_slot}})
            $fatal(1,"bank local priority bank/parity=%0d actual=%h",n,selected_ids);
    end
    for(n=0;n<2;n=n+1)begin
        reset_both;
        for(j=0;j<96;j=j+1)slot(2*j+n,20+n,3,1,0);
        request(20+n,20+n,3*64+4,4000+n);finish_lookup;
        expected_slot=190+n;
        if(selected_ids!=={4{expected_slot}})$fatal(1,"global bank priority parity=%0d actual=%h",n,selected_ids);
    end
    $display("P7_BANK_COVERAGE PASS slots=192 public_alloc=192 fetch=192 public_load=192 repeat_hit=192 local_priority=24 global_priority=2");
    $display("P7_BANKS_EQUIVALENCE PASS tests=%0d edges=%0d done=%0d alloc=%0d blocked=%0d touch_done=%0d touch_alloc=%0d touch_elig=%0d allhit=%0d",tests,compared_edges,completed,allocations,blocked_allocations,done_touch,alloc_touch,elig_touch,allhit_cycles);
    $finish;
end
initial begin #2000000;$fatal(1,"watchdog");end

endmodule

`timescale 1ns/1ps
module segment_cache_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,clear=0,lookup=0,touch=0,sample=0;
    reg [10:0] qa=0,qb=0,qx=0,sx=0;
    reg [21:0] seq=0,retired=0;
    reg [31:0] ids=0,touch_ids=0;
    reg [21:0] touch_seq=0;
    wire busy,done,ready,fetch;
    wire [7:0] a0,a1,b0,b1,fb;
    wire [10:0] fr;
    wire [4:0] fs;
    wire load_done,load_error,sv;
    wire [15:0] p00,p01,p10,p11;
    reg rv=0,rl=0,active=0,enable=1,negative=0;
    reg [255:0] data=0;
    integer tick=0,beat=0,row=0,seg=0,delay_count=0,first_delay=2;
    integer loads=0,errors=0,bad_kind=0,cases=0,n,j,c,xx,timeout,snapshot,err_before;
    reg [31:0] pip_ids[0:63];
    reg [31:0] pinned_ids;
    wire grant=rst_n && enable && !active;
    wire accept=fetch && grant;
    undistort_cache_ab dut(
        .clk(clk),.rst_n(rst_n),.i_frame_clear(clear),.i_line_mode(1'b0),
        .i_load_begin(accept),.i_load_bank(fb),.i_load_row(fr),
        .i_load_vld(rv),.i_load_data(data),.i_load_last(rl),
        .o_load_done(load_done),.o_load_error(load_error),
        .i_query_row_a(11'd0),.i_query_row_b(11'd0),.i_prefetch_row(11'd0),
        .i_sample_req(sample),.i_sample_bank_a(ids[7:0]),.i_sample_bank_a1(ids[15:8]),
        .i_sample_bank_b(ids[23:16]),.i_sample_bank_b1(ids[31:24]),.i_sample_x(sx),
        .o_sample_valid(sv),.o_p00(p00),.o_p01(p01),.o_p10(p10),.o_p11(p11),
        .i_lookup_req(lookup),.i_lookup_a(qa),.i_lookup_b(qb),.i_lookup_x(qx),
        .i_lookup_seq(seq),.o_lookup_busy(busy),.o_lookup_done(done),
        .o_id_a0(a0),.o_id_a1(a1),.o_id_b0(b0),.o_id_b1(b1),
        .i_touch(touch),.i_touch_ids(touch_ids),.i_touch_seq(touch_seq),
        .i_retired_count(retired),.i_ready_ids(ids),.o_ids_ready(ready),
        .o_fetch_req(fetch),.o_fetch_bank(fb),.o_fetch_row(fr),.o_fetch_seg(fs),.i_fetch_gnt(grant));
undistort_cache_ab_reference ref_dut(
        .clk(clk),.rst_n(rst_n),.i_frame_clear(clear),.i_line_mode(1'b0),
        .i_load_begin(accept),.i_load_bank(fb),.i_load_row(fr),
        .i_load_vld(rv),.i_load_data(data),.i_load_last(rl),
        .o_load_done(),.o_load_error(),
        .i_query_row_a(11'd0),.i_query_row_b(11'd0),.i_prefetch_row(11'd0),
        .i_sample_req(sample),.i_sample_bank_a(ids[7:0]),.i_sample_bank_a1(ids[15:8]),
        .i_sample_bank_b(ids[23:16]),.i_sample_bank_b1(ids[31:24]),.i_sample_x(sx),
        .o_sample_valid(),.o_p00(),.o_p01(),.o_p10(),.o_p11(),
        .i_lookup_req(lookup),.i_lookup_a(qa),.i_lookup_b(qb),.i_lookup_x(qx),
        .i_lookup_seq(seq),.o_lookup_busy(),.o_lookup_done(),
        .o_id_a0(),.o_id_a1(),.o_id_b0(),.o_id_b1(),
        .i_touch(touch),.i_touch_ids(touch_ids),.i_touch_seq(touch_seq),
        .i_retired_count(retired),.i_ready_ids(ids),.o_ids_ready(),
        .o_fetch_req(),.o_fetch_bank(),.o_fetch_row(),.o_fetch_seg(),.i_fetch_gnt(grant));

integer compared_edges=0,completed=0,allocations=0,blocked_allocations=0;
integer done_touch=0,alloc_touch=0,elig_touch=0,cmp_i;
reg [191:0] expected_mask;
always @(posedge clk)begin
    if(rst_n && !dut.i_frame_clear)begin
        if(dut.qstate==6)begin
            expected_mask=0;
            for(cmp_i=0;cmp_i<4;cmp_i=cmp_i+1)expected_mask[dut.qid[cmp_i]]=1;
            if(dut.done_mask!==expected_mask)$fatal(1,"MASK mismatch before DONE");
            completed=completed+1;
            if(dut.i_touch)done_touch=done_touch+1;
        end
        if(dut.qstate==5)begin
            if(dut.chosen_ok)begin allocations=allocations+1;if(dut.i_touch)alloc_touch=alloc_touch+1;end
            else blocked_allocations=blocked_allocations+1;
        end
        if(dut.qstate==7 && dut.i_touch)elig_touch=elig_touch+1;
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
    for(cmp_i=0;cmp_i<256;cmp_i=cmp_i+1)
        if(dut.fetch_fifo[cmp_i]!==ref_dut.fetch_fifo[cmp_i])$fatal(1,"fetch FIFO mismatch");
    if((!rst_n || dut.i_frame_clear) && dut.done_mask!==192'd0)$fatal(1,"MASK reset/clear failure");
    // P2 invariant: all selected future hits and allocated slots are retained.
    if(rst_n && !dut.i_frame_clear && (dut.qstate==3 || dut.qstate==4 ||
       dut.qstate==5 || dut.qstate==6 || dut.qstate==7 || dut.qstate==8))begin
        expected_mask=0;
        for(cmp_i=0;cmp_i<4;cmp_i=cmp_i+1)
            if(ref_dut.qfound[cmp_i])expected_mask[ref_dut.qid[cmp_i]]=1;
        if(dut.done_mask!==expected_mask)$fatal(1,"P2_MASK selected/allocated set mismatch");
    end

end

    function [15:0] pixel;
        input integer r,x;
        reg [4:0] blue;
        begin blue=r+x;pixel={r[4:0],x[5:0],blue};end
    endfunction
    always @(posedge clk)begin
        tick=tick+1;rv<=0;rl<=0;
        if(!rst_n)active<=0;
        else begin
            if(load_error)begin
                errors=errors+1;
                if(!negative)$fatal(1,"Unexpected cache error");
            end
            if(accept)begin
                if(active)$fatal(1,"multiple outstanding transactions");
                row=fr;seg=fs;beat=0;delay_count=first_delay;active<=1;loads=loads+1;
            end else if(active)begin
                if(delay_count>0)delay_count=delay_count-1;
                else if(tick%11!=0)begin
                    rv<=1;
                    for(integer lane=0;lane<16;lane=lane+1)
                        data[lane*16+:16]<=pixel(row,seg*64+beat*16+lane);
                    rl<=(bad_kind==1)?1'b1:((bad_kind==2)?1'b0:(beat==3));
                    if(beat==3 || bad_kind==1)active<=0;
                    else beat=beat+1;
                end
            end
        end
    end
    task get_ids;
        input integer rowa,rowb,x;
        begin
            @(negedge clk);qa=rowa;qb=rowb;qx=x;lookup=1;
            @(negedge clk);lookup=0;
            timeout=0;
            while(!done && timeout<1000)begin @(negedge clk);timeout=timeout+1;end
            if(!done)$fatal(1,"lookup timeout seq=%0d",seq);
            ids={b1,b0,a1,a0};#1;
        end
    endtask
    task wait_ready;
        begin
            #1;
            timeout=0;
            while(!ready && timeout<1000)begin @(negedge clk);timeout=timeout+1;end
            if(!ready)$fatal(1,"data not ready");
        end
    endtask
    task sample_check;
        input integer rowa,rowb,x;
        integer nx;
        begin
            nx=x==1919?1919:x+1;
            seq=seq+1;get_ids(rowa,rowb,x);wait_ready;
            @(negedge clk);sx=x;sample=1;
            @(negedge clk);sample=0;
            timeout=0;
            while(!sv && timeout<10)begin @(negedge clk);timeout=timeout+1;end
            if(!sv || p00!==pixel(rowa,x) || p01!==pixel(rowa,nx) ||
               p10!==pixel(rowb,x) || p11!==pixel(rowb,nx))
                $fatal(1,"sample mismatch x=%0d rows=%0d,%0d ids=%h got=%h,%h,%h,%h exp=%h,%h,%h,%h",x,rowa,rowb,ids,p00,p01,p10,p11,pixel(rowa,x),pixel(rowa,nx),pixel(rowb,x),pixel(rowb,nx));
            cases=cases+1;
        end
    endtask
    task clear_cache;
        begin
            wait(!active && !fetch);repeat(3)@(negedge clk);
            clear=1;@(negedge clk);clear=0;
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        // Seven directed samples from the frozen cache72 coverage, via real
        // lookup/allocation/short-block loading rather than forced bank numbers.
        sample_check(10,11,0);sample_check(10,11,15);
        sample_check(12,13,16);sample_check(12,13,1918);sample_check(12,13,1919);
        sample_check(14,11,1023);sample_check(14,14,1919);
        // New cache supports rowA=rowB by sharing the actual sample word.
        for(n=0;n<64;n=n+1)begin
            seq=seq+1;get_ids(14,11,(n*31)%1920);wait_ready;
            pip_ids[n]=ids;
        end
        n=0;@(negedge clk);
        for(c=0;c<134;c=c+1)begin
            sample=(c<128 && c%2==0);
            ids=pip_ids[(c/2)%64];sx=((c/2)*31)%1920;
            @(posedge clk);#1;
            if(sv)begin
                xx=(n*31)%1920;
                if(n>=64 || p00!==pixel(14,xx) || p01!==pixel(14,xx+1) ||
                    p10!==pixel(11,xx) || p11!==pixel(11,xx+1))
                    $fatal(1,"pipeline mismatch n=%0d",n);
                n=n+1;cases=cases+1;
            end
            @(negedge clk);
        end
        sample=0;if(n!=64)$fatal(1,"pipeline count");
        clear_cache;cases=cases+1;
        if(ready)$fatal(1,"clear did not invalidate tags");
        if(cases!=72)$fatal(1,"cache72 coverage count");
        $display("SEGMENT_CACHE cache72_equivalent PASS samples=72");
        // Horizontal 64px boundary: all four banks must be available.
        retired=seq+1;sample_check(20,19,63);retired=seq+1;
        snapshot=loads;sample_check(20,19,63);
        if(loads!=snapshot)$fatal(1,"duplicate fetch");
        retired=seq+1;sample_check(0,0,1919);
        if(ids[7:0]!=ids[15:8] || ids[7:0]!=ids[23:16] || ids[7:0]!=ids[31:24])
            $fatal(1,"clamped neighbours not deduplicated");
        // Pin a segment while enough misses force both parity pools to replace.
        pinned_ids=ids;
        @(negedge clk);touch=1;touch_ids=ids;touch_seq=22'd30000;
        @(negedge clk);touch=0;
        for(n=0;n<110;n=n+1)begin
            retired=seq+1;sample_check(200+2*n,199+2*n,64*(n%30));
        end
        ids=pinned_ids;
        if(!ready || dut.tag_row[ids[7:0]]!=0 || dut.tag_seg[ids[7:0]]!=29)
            $fatal(1,"replacement overwrote pinned segment");
        // Ready must remain low during a deliberately delayed full load.
        retired=30001;seq=30001;first_delay=64;
        get_ids(700,699,63);
        if(ready)$fatal(1,"partial segment published");
        wait_ready;first_delay=0;
        // Early and missing LAST must invalidate rather than publish data.
        for(n=1;n<=2;n=n+1)begin
            clear_cache;negative=1;bad_kind=n;err_before=errors;
            seq=seq+1;get_ids(800+n*2,799+n*2,128);
            repeat(30)@(negedge clk);
            if(errors<=err_before || ready)$fatal(1,"bad LAST not rejected");
            wait(!active && !fetch);bad_kind=0;
            clear_cache;negative=0;
        end
        // A reset with queued fetches clears both ownership and tag visibility.
        enable=0;seq=seq+1;get_ids(900,899,63);
        if(!fetch)$fatal(1,"expected pending fetch");
        @(negedge clk);rst_n=0;repeat(3)@(negedge clk);rst_n=1;enable=1;
        if(fetch || busy || ready)$fatal(1,"reset did not clear pending state");
        seq=0;retired=0;sample_check(0,0,0);
        $display("SEGMENT_CACHE PASS cache72=72 total_samples=%0d negative_errors=%0d loads=%0d",cases,errors,loads);
        $finish;
    end
    initial begin #10000000;$fatal(1,"SEGMENT_CACHE TIMEOUT");end
endmodule

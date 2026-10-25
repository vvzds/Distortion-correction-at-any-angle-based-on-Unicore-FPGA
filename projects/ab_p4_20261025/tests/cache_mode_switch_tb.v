`timescale 1ns/1ps
// Verify both cache geometries reuse storage safely across frame clears.
module cache_mode_switch_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,clear=0,line_mode=1,manual_begin=0,manual_vld=0,manual_last=0;
    reg [7:0] manual_bank=0;
    reg [10:0] manual_row=0,qa=0,qb=1,sx=0;
    reg [255:0] manual_data=0,segment_data=0;
    reg segment_vld=0,segment_last=0,active=0,lookup=0,sample=0;
    reg [31:0] ids=0;
    integer seed=0,segment_seed=0,row=0,seg=0,beat=0,lane,checks=0,loads=0,timeout;
    wire fetch,done,ready,sv,hit_a,hit_b,load_error;
    wire [7:0] fb,a0,a1,b0,b1,bank_a,bank_b;
    wire [10:0] fr;
    wire [4:0] fs;
    wire [15:0] p00,p01,p10,p11;
    wire accept=fetch && !active && !line_mode;
    undistort_cache_ab dut(
        .clk(clk),.rst_n(rst_n),.i_frame_clear(clear),.i_line_mode(line_mode),
        .i_load_begin(line_mode?manual_begin:accept),
        .i_load_bank(line_mode?manual_bank:fb),.i_load_row(line_mode?manual_row:fr),
        .i_load_vld(line_mode?manual_vld:segment_vld),
        .i_load_data(line_mode?manual_data:segment_data),
        .i_load_last(line_mode?manual_last:segment_last),.o_load_error(load_error),
        .i_query_row_a(qa),.i_query_row_b(qb),.i_prefetch_row(11'd0),
        .o_hit_a(hit_a),.o_hit_b(hit_b),.o_bank_a(bank_a),.o_bank_b(bank_b),
        .i_sample_req(sample),.i_sample_bank_a(line_mode?bank_a:ids[7:0]),
        .i_sample_bank_b(line_mode?bank_b:ids[23:16]),
        .i_sample_bank_a1(ids[15:8]),.i_sample_bank_b1(ids[31:24]),.i_sample_x(sx),
        .o_sample_valid(sv),.o_p00(p00),.o_p01(p01),.o_p10(p10),.o_p11(p11),
        .i_lookup_req(lookup),.i_lookup_a(qa),.i_lookup_b(qb),.i_lookup_x(sx),
        .i_lookup_seq(22'd0),.o_lookup_done(done),
        .o_id_a0(a0),.o_id_a1(a1),.o_id_b0(b0),.o_id_b1(b1),
        .i_touch(1'b0),.i_touch_ids(32'd0),.i_touch_seq(22'd0),
        .i_retired_count(22'd0),.i_ready_ids(ids),.o_ids_ready(ready),
        .o_fetch_req(fetch),.o_fetch_bank(fb),.o_fetch_row(fr),.o_fetch_seg(fs),
        .i_fetch_gnt(accept));
undistort_cache_ab_reference ref_dut(
        .clk(clk),.rst_n(rst_n),.i_frame_clear(clear),.i_line_mode(line_mode),
        .i_load_begin(line_mode?manual_begin:accept),
        .i_load_bank(line_mode?manual_bank:fb),.i_load_row(line_mode?manual_row:fr),
        .i_load_vld(line_mode?manual_vld:segment_vld),
        .i_load_data(line_mode?manual_data:segment_data),
        .i_load_last(line_mode?manual_last:segment_last),.o_load_error(),
        .i_query_row_a(qa),.i_query_row_b(qb),.i_prefetch_row(11'd0),
        .o_hit_a(),.o_hit_b(),.o_bank_a(),.o_bank_b(),
        .i_sample_req(sample),.i_sample_bank_a(line_mode?bank_a:ids[7:0]),
        .i_sample_bank_b(line_mode?bank_b:ids[23:16]),
        .i_sample_bank_a1(ids[15:8]),.i_sample_bank_b1(ids[31:24]),.i_sample_x(sx),
        .o_sample_valid(),.o_p00(),.o_p01(),.o_p10(),.o_p11(),
        .i_lookup_req(lookup),.i_lookup_a(qa),.i_lookup_b(qb),.i_lookup_x(sx),
        .i_lookup_seq(22'd0),.o_lookup_done(),
        .o_id_a0(),.o_id_a1(),.o_id_b0(),.o_id_b1(),
        .i_touch(1'b0),.i_touch_ids(32'd0),.i_touch_seq(22'd0),
        .i_retired_count(22'd0),.i_ready_ids(ids),.o_ids_ready(),
        .o_fetch_req(),.o_fetch_bank(),.o_fetch_row(),.o_fetch_seg(),
        .i_fetch_gnt(accept));

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
end

    function [15:0] pixel;
        input integer s,r,x;
        begin pixel=(s*7919)^(r*193)^x;end
    endfunction
    always @(posedge clk)begin
        segment_vld<=0;segment_last<=0;
        if(rst_n && load_error)$fatal(1,"cache mode-switch load error");
        if(accept)begin
            active<=1;row=fr;seg=fs;beat=0;segment_seed=seed;loads=loads+1;
        end else if(active)begin
            segment_vld<=1;segment_last<=beat==3;
            for(lane=0;lane<16;lane=lane+1)
                segment_data[16*lane+:16]<=pixel(segment_seed,row,seg*64+beat*16+lane);
            if(beat==3)active<=0;else beat=beat+1;
        end
    end
    task line_load;
        input integer r,b;
        integer n,l;
        begin
            @(negedge clk);manual_row=r;manual_bank=b;manual_begin=1;
            @(negedge clk);manual_begin=0;
            for(n=0;n<120;n=n+1)begin
                manual_vld=1;manual_last=n==119;
                for(l=0;l<16;l=l+1)manual_data[16*l+:16]=pixel(seed,r,16*n+l);
                @(negedge clk);
            end
            manual_vld=0;manual_last=0;repeat(2)@(negedge clk);
        end
    endtask
    task check_sample;
        input integer x;
        integer nx;
        begin
            nx=x==1919?1919:x+1;
            @(negedge clk);sx=x;
            if(!line_mode)begin
                lookup=1;@(negedge clk);lookup=0;timeout=0;
                while(!done && timeout<1000)begin @(negedge clk);timeout=timeout+1;end
                if(!done)$fatal(1,"mode-switch lookup timeout");
                ids={b1,b0,a1,a0};#1;timeout=0;
                while(!ready && timeout<1000)begin @(negedge clk);timeout=timeout+1;end
                if(!ready)$fatal(1,"mode-switch fetch timeout");
            end else if(!hit_a || !hit_b)$fatal(1,"mode-switch missing line");
            @(negedge clk);sample=1;@(negedge clk);sample=0;timeout=0;
            while(!sv && timeout<10)begin @(negedge clk);timeout=timeout+1;end
            if(!sv || p00!==pixel(seed,qa,x) || p01!==pixel(seed,qa,nx) ||
               p10!==pixel(seed,qb,x) || p11!==pixel(seed,qb,nx))
                $fatal(1,"stale shared RAM data mode=%0d seed=%0d x=%0d",line_mode,seed,x);
            checks=checks+1;
        end
    endtask
    task new_frame;
        input new_mode;
        begin
            wait(!active && !fetch);repeat(4)@(negedge clk);
            clear=1;line_mode=new_mode;seed=seed+1;
            @(negedge clk);clear=0;#1;
            if(hit_a || hit_b || ready || fetch || sv)
                $fatal(1,"frame clear retained prior geometry visibility");
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        line_load(0,0);line_load(1,1);
        check_sample(0);check_sample(63);check_sample(1919);
        new_frame(0);check_sample(63);check_sample(1919);
        new_frame(1);qa=2;qb=1;line_load(2,2);line_load(1,1);
        check_sample(0);check_sample(63);check_sample(1919);
        new_frame(0);check_sample(63);check_sample(1919);
        if(checks!=10 || loads!=12)$fatal(1,"mode-switch coverage incomplete");
        $display("CACHE_MODE_SWITCH PASS checks=%0d segment_loads=%0d transitions=3",checks,loads);
        $finish;
    end
    initial begin #1000000;$fatal(1,"cache mode-switch timeout");end
endmodule

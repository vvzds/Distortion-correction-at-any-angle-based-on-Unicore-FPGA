`timescale 1ns/1ps
module undistort_line_cache_tb;
    reg clk=0, rst_n=0, i_frame_clear=0;
    reg i_load_begin=0, i_load_vld=0, i_load_last=0;
    reg [7:0] i_load_bank=0;
    reg [10:0] i_load_row=0;
    reg [255:0] i_load_data=0;
    wire o_load_done,o_load_error;
    reg [10:0] i_query_row_a=0,i_query_row_b=0;
    wire o_hit_a,o_hit_b;
    wire [7:0] o_bank_a,o_bank_b;
    reg i_sample_req=0;
    reg [7:0] i_sample_bank_a=0,i_sample_bank_b=0;
    reg [10:0] i_sample_x=0;
    wire o_sample_valid;
    wire [15:0] o_p00,o_p01,o_p10,o_p11;
    integer err=0, checks=0, fd;
    integer beat,pix,timeout;
    reg [255:0] packed_data;

    undistort_cache_ab dut(
        .i_line_mode(1'b1),.i_sample_bank_a1(8'd0),.i_sample_bank_b1(8'd0),
        .i_lookup_req(1'b0),.i_lookup_a(11'd0),.i_lookup_b(11'd0),.i_lookup_x(11'd0),
        .i_lookup_seq(22'd0),.i_touch(1'b0),.i_touch_ids(32'd0),
        .i_touch_seq(22'd0),.i_retired_count(22'd0),.i_ready_ids(32'd0),.i_fetch_gnt(1'b0),
        .clk(clk),.rst_n(rst_n),.i_frame_clear(i_frame_clear),
        .i_load_begin(i_load_begin),
        .i_load_bank(i_load_bank),.i_load_row(i_load_row),
        .i_load_vld(i_load_vld),.i_load_data(i_load_data),
        .i_load_last(i_load_last),.o_load_done(o_load_done),
        .o_load_error(o_load_error),
        .i_query_row_a(i_query_row_a),.i_query_row_b(i_query_row_b),
        .o_hit_a(o_hit_a),.o_hit_b(o_hit_b),
        .o_bank_a(o_bank_a),.o_bank_b(o_bank_b),
        .i_prefetch_row(11'd0),.o_prefetch_hit(),
        .i_sample_req(i_sample_req),.i_sample_bank_a(i_sample_bank_a),
        .i_sample_bank_b(i_sample_bank_b),.i_sample_x(i_sample_x),
        .o_sample_valid(o_sample_valid),
        .o_p00(o_p00),.o_p01(o_p01),.o_p10(o_p10),.o_p11(o_p11)
    );
undistort_cache_ab_reference ref_dut(
        .i_line_mode(1'b1),.i_sample_bank_a1(8'd0),.i_sample_bank_b1(8'd0),
        .i_lookup_req(1'b0),.i_lookup_a(11'd0),.i_lookup_b(11'd0),.i_lookup_x(11'd0),
        .i_lookup_seq(22'd0),.i_touch(1'b0),.i_touch_ids(32'd0),
        .i_touch_seq(22'd0),.i_retired_count(22'd0),.i_ready_ids(32'd0),.i_fetch_gnt(1'b0),
        .clk(clk),.rst_n(rst_n),.i_frame_clear(i_frame_clear),
        .i_load_begin(i_load_begin),
        .i_load_bank(i_load_bank),.i_load_row(i_load_row),
        .i_load_vld(i_load_vld),.i_load_data(i_load_data),
        .i_load_last(i_load_last),.o_load_done(),
        .o_load_error(),
        .i_query_row_a(i_query_row_a),.i_query_row_b(i_query_row_b),
        .o_hit_a(),.o_hit_b(),
        .o_bank_a(),.o_bank_b(),
        .i_prefetch_row(11'd0),.o_prefetch_hit(),
        .i_sample_req(i_sample_req),.i_sample_bank_a(i_sample_bank_a),
        .i_sample_bank_b(i_sample_bank_b),.i_sample_x(i_sample_x),
        .o_sample_valid(),
        .o_p00(),.o_p01(),.o_p10(),.o_p11()
    );

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

    always #4 clk=~clk;

    function [15:0] pixel;
        input integer row,x;
        reg [4:0] blue;
        begin
            blue=row+x;
            pixel={row[4:0],x[5:0],blue};
        end
    endfunction
    task send_row;
        input integer bank,row,gap;
        begin
            @(negedge clk);
            i_load_bank=bank; i_load_row=row; i_load_begin=1;
            @(negedge clk); i_load_begin=0;
            for(beat=0;beat<120;beat=beat+1) begin
                packed_data=0;
                for(pix=0;pix<16;pix=pix+1)
                    packed_data[16*pix +: 16]=pixel(row,beat*16+pix);
                i_load_data=packed_data;
                i_load_vld=1;
                i_load_last=(beat==119);
                @(posedge clk); #1;
                if(beat==119 && o_load_done !== 1) err=err+1;
                @(negedge clk);
                i_load_vld=0; i_load_last=0;
                if(gap && beat%13==0) @(negedge clk);
            end
            if(o_load_error !== 0) err=err+1;
        end
    endtask
    task sample_check;
        input integer row_a,row_b,bank_a,bank_b,x;
        integer xn;
        begin
            xn=(x==1919)?1919:x+1;
            i_query_row_a=row_a; i_query_row_b=row_b;
            #1;
            if(o_hit_a !== 1 || o_hit_b !== 1 ||
               o_bank_a !== bank_a || o_bank_b !== bank_b) err=err+1;
            @(negedge clk);
            i_sample_bank_a=bank_a; i_sample_bank_b=bank_b;
            i_sample_x=x; i_sample_req=1;
            @(negedge clk); i_sample_req=0;
            timeout=0;
            while(o_sample_valid !== 1 && timeout<10) begin
                @(posedge clk); #1; timeout=timeout+1;
            end
            if(o_sample_valid !== 1 || o_p00 !== pixel(row_a,x) ||
               o_p01 !== pixel(row_a,xn) || o_p10 !== pixel(row_b,x) ||
               o_p11 !== pixel(row_b,xn)) begin
                $display("FAIL: sample x=%0d rowA=%0d rowB=%0d",x,row_a,row_b);
                err=err+1;
            end
            checks=checks+1;
        end
    endtask

    // 连续每两拍提交一组，验证新请求与旧结果重叠时不会串像素。
    task pipeline_check;
        integer c,n,xx;
        begin
            n=0;
            @(negedge clk);
            for(c=0;c<134;c=c+1) begin
                i_sample_req=(c<128 && c%2==0);
                i_sample_bank_a=0;i_sample_bank_b=1;
                i_sample_x=((c/2)*31)%1920;
                @(posedge clk);#1;
                if(o_sample_valid) begin
                    xx=(n*31)%1920;
                    if(n>=64 || o_p00!==pixel(14,xx) || o_p01!==pixel(14,xx+1) ||
                       o_p10!==pixel(11,xx) || o_p11!==pixel(11,xx+1)) err=err+1;
                    n=n+1;checks=checks+1;
                end
                @(negedge clk);
            end
            i_sample_req=0;
            if(n!=64) err=err+1;
        end
    endtask

    initial begin
        #100000;
        $display("FAIL: watchdog timeout");
        $finish;
    end
    initial begin
        fd=$fopen("line_cache_result.txt","w");
        repeat(4) @(negedge clk); rst_n=1;
        i_query_row_a=10; i_query_row_b=11;
        #1;
        if(o_hit_a !== 0 || o_hit_b !== 0) err=err+1;
        send_row(0,10,0);
        send_row(1,11,1);
        send_row(2,12,0);
        send_row(3,13,1);
        sample_check(10,11,0,1,0);
        sample_check(10,11,0,1,15);
        sample_check(12,13,2,3,16);
        sample_check(12,13,2,3,1918);
        sample_check(12,13,2,3,1919);
        send_row(0,14,0);
        i_query_row_a=10; i_query_row_b=14;
        #1;
        if(o_hit_a !== 0 || o_hit_b !== 1 || o_bank_b !== 0) err=err+1;
        sample_check(14,11,0,1,1023);
        sample_check(14,14,0,0,1919);
        pipeline_check();
        @(negedge clk); i_load_begin=1; i_load_bank=2; i_load_row=15;
        @(negedge clk); i_load_begin=0; i_load_vld=1; i_load_last=1;
        @(posedge clk); #1;
        if(o_load_error !== 1 || o_load_done !== 0) err=err+1;
        @(negedge clk); i_load_vld=0; i_load_last=0;
        i_query_row_a=15; #1;
        if(o_hit_a !== 0) err=err+1;
        i_query_row_a=14; i_query_row_b=11; #1;
        if(o_hit_a !== 1 || o_hit_b !== 1) err=err+1;
        @(negedge clk); i_frame_clear=1;
        @(negedge clk); i_frame_clear=0;
        #1;
        if(o_hit_a !== 0 || o_hit_b !== 0) err=err+1;
        checks=checks+1;
        if(err==0 && checks==72) begin
            $display("=== ALL TESTS PASSED (err=0) ===");
            $fdisplay(fd,"=== ALL TESTS PASSED (err=0) === samples=%0d",checks);
        end else begin
            $display("=== TEST FAILED: err=%0d ===",err);
            $fdisplay(fd,"=== TEST FAILED: err=%0d samples=%0d ===",err,checks);
        end
        $fclose(fd);
        $finish;
    end
endmodule

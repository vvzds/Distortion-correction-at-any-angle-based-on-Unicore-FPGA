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

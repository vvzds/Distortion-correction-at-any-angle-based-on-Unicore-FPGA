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

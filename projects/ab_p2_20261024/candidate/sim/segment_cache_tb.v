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

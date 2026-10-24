`timescale 1ns/1ps
// R3: DDR model deliberately survives cache-local clear/reset. Accepted old
// responses are returned, not deleted. A single-outstanding model prevents
// accepting a new load until that old logical burst has actually drained.
module cache_boundary_r3_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,clear=0,lookup=0,sample=0;
    reg [10:0] qa=0,qb=1,qx=0,sx=0;
    reg [21:0] seq=0;
    reg [31:0] ids=0,resident_ids=0,new_ids=0;
    wire busy,done,ready,fetch,ldone,lerror,sv;
    wire [7:0] a0,a1,b0,b1,fb;
    wire [10:0] fr;wire [4:0] fs;
    wire [15:0] p00,p01,p10,p11;
    reg allow_grant=1,pause_return=1,active=0,rv=0,rl=0;
    reg [255:0] data=0;
    integer seed=1,saved_seed=0,row=0,seg=0,beat=0,delay_left=0;
    integer first_delay=12,beat_gap=8,loads=0,returns=0,errors=0,dones=0;
    integer late_phase=0,late_clear=0,late_reset=0,checks=0,snapshot=0,timeout=0;
    integer overlap_begin=0,overlap_input=0,overlap_ram=0,overlap_last=0;
    wire grant=rst_n && allow_grant && !active && !rv;
    wire accept=fetch && grant;
    undistort_cache_ab dut(
        .clk(clk),.rst_n(rst_n),.i_frame_clear(clear),.i_line_mode(1'b0),
        .i_load_begin(accept),.i_load_bank(fb),.i_load_row(fr),
        .i_load_vld(rv),.i_load_data(data),.i_load_last(rl),
        .o_load_done(ldone),.o_load_error(lerror),
        .i_query_row_a(11'd0),.i_query_row_b(11'd1),.i_prefetch_row(11'd0),
        .i_sample_req(sample),.i_sample_bank_a(ids[7:0]),.i_sample_bank_a1(ids[15:8]),
        .i_sample_bank_b(ids[23:16]),.i_sample_bank_b1(ids[31:24]),.i_sample_x(sx),
        .o_sample_valid(sv),.o_p00(p00),.o_p01(p01),.o_p10(p10),.o_p11(p11),
        .i_lookup_req(lookup),.i_lookup_a(qa),.i_lookup_b(qb),.i_lookup_x(qx),
        .i_lookup_seq(seq),.o_lookup_busy(busy),.o_lookup_done(done),
        .o_id_a0(a0),.o_id_a1(a1),.o_id_b0(b0),.o_id_b1(b1),
        .i_touch(1'b0),.i_touch_ids(32'd0),.i_touch_seq(22'd0),
        .i_retired_count(22'd0),.i_ready_ids(ids),.o_ids_ready(ready),
        .o_fetch_req(fetch),.o_fetch_bank(fb),.o_fetch_row(fr),.o_fetch_seg(fs),.i_fetch_gnt(grant));
    function [15:0] pixel;
        input integer version,r,x;
        begin pixel=(version*7919)^(r*193)^x;end
    endfunction
    // No reset branch here: an already accepted transaction remains alive.
    always @(posedge clk)begin
        rv<=0;rl<=0;
        if(accept)begin
            if(active)$fatal(1,"R3 model multiple outstanding");
            row=fr;seg=fs;saved_seed=seed;beat=0;delay_left=first_delay;
            active<=1;loads=loads+1;
        end else if(active && !pause_return)begin
            if(delay_left>0)delay_left=delay_left-1;
            else begin
                rv<=1;rl<=beat==3;
                for(integer lane=0;lane<16;lane=lane+1)
                    data[16*lane+:16]<=pixel(saved_seed,row,seg*64+beat*16+lane);
                if(beat==3)active<=0;
                else begin beat=beat+1;delay_left=beat_gap-1;end
            end
        end
        if(rst_n)begin
            if(rv)begin
                returns=returns+1;
                if(late_phase==1)late_clear=late_clear+1;
                if(late_phase==2)late_reset=late_reset+1;
            end
            if(lerror)begin
                errors=errors+1;
                if(late_phase==0)$fatal(1,"R3 unexpected cache rejection");
            end
            if(ldone)dones=dones+1;
            if(sample && accept)overlap_begin=overlap_begin+1;
            if(sample && rv)overlap_input=overlap_input+1;
            if(sample && rv && rl)overlap_last=overlap_last+1;
            if(dut.load_ok && dut.read_enable)begin
                overlap_ram=overlap_ram+1;
                if((!dut.write_parity && dut.write_index==dut.even_addr) ||
                   (dut.write_parity && dut.write_index==dut.odd_addr))
                    $fatal(1,"R3 RAM read/write alias while resident pixel is pinned");
            end
        end
    end
    task get_ids;
        input integer r0,r1,x;
        begin
            @(negedge clk);qa=r0;qb=r1;qx=x;seq=seq+1;lookup=1;
            @(negedge clk);lookup=0;timeout=0;
            while(!done && timeout<1000)begin @(negedge clk);timeout=timeout+1;end
            if(!done)$fatal(1,"R3 lookup timeout");
            ids={b1,b0,a1,a0};#1;
        end
    endtask
    task wait_ready;
        begin
            timeout=0;#1;
            while(!ready && timeout<2000)begin @(negedge clk);timeout=timeout+1;end
            if(!ready)$fatal(1,"R3 load timeout");
        end
    endtask
    task result_check;
        input integer r0,r1,x;
        integer nx;
        begin
            nx=x==1919?1919:x+1;timeout=0;
            while(!sv && timeout<12)begin @(negedge clk);timeout=timeout+1;end
            if(!sv || p00!==pixel(seed,r0,x) || p01!==pixel(seed,r0,nx) ||
               p10!==pixel(seed,r1,x) || p11!==pixel(seed,r1,nx))
                $fatal(1,"R3 stale/mixed pixel version=%0d got=%h,%h,%h,%h",seed,p00,p01,p10,p11);
            checks=checks+1;
        end
    endtask
    task pulse_sample;
        input integer r0,r1,x;
        begin
            sx=x;sample=1;@(negedge clk);sample=0;result_check(r0,r1,x);
        end
    endtask
    task late_case;
        input integer do_reset;
        begin
            pause_return=1;allow_grant=1;
            get_ids(40+do_reset*2,39+do_reset*2,63);
            wait(active);@(negedge clk);allow_grant=0;
            if(!dut.load_active)$fatal(1,"R3 old read was not accepted by cache");
            snapshot=dones;late_phase=do_reset?2:1;
            if(do_reset)begin rst_n=0;repeat(3)@(negedge clk);rst_n=1;end
            else begin clear=1;@(negedge clk);clear=0;end
            #1;
            if(dut.load_active || dut.tag_ready!=0 || fetch || ready)
                $fatal(1,"R3 clear/reset retained old visibility");
            seed=seed+1;
            // Queue a new generation while the old accepted burst is held.
            // No new load may be accepted before that old burst drains.
            get_ids(40+do_reset*2,39+do_reset*2,63);
            if(ready || !fetch)$fatal(1,"R3 expected unready new-generation queue");
            pause_return=0;
            wait(!active && !rv);repeat(3)@(negedge clk);
            if(ready || dones!=snapshot || dut.tag_ready!=0)
                $fatal(1,"R3 old response published as new generation");
            if((do_reset?late_reset:late_clear)!=4)$fatal(1,"R3 old response coverage incomplete");
            late_phase=0;allow_grant=1;wait_ready;
            @(negedge clk);pulse_sample(40+do_reset*2,39+do_reset*2,63);
            wait(!active && !rv && !fetch);repeat(3)@(negedge clk);
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        late_case(0);late_case(1);
        clear=1;@(negedge clk);clear=0;seed=5;
        get_ids(0,1,15);wait_ready;resident_ids=ids;
        wait(!active && !rv && !fetch);@(negedge clk);
        allow_grant=0;get_ids(20,21,128);new_ids=ids;
        ids=resident_ids;#1;if(!ready)$fatal(1,"R3 resident IDs not ready");
        @(negedge clk);allow_grant=1;pulse_sample(0,1,15);
        while(!(rv && !rl))@(negedge clk);
        pulse_sample(0,1,15);
        while(!(rv && rl))@(negedge clk);
        pulse_sample(0,1,15);
        // Arrange actual synchronous RAM reads to overlap a subsequent write.
        while(!(active && delay_left==1))@(negedge clk);
        pulse_sample(0,1,15);
        ids=new_ids;wait_ready;wait(!active && !rv && !fetch);
        repeat(5)@(negedge clk);
        if(late_clear!=4 || late_reset!=4 || errors!=8 || checks!=6 ||
           overlap_begin<1 || overlap_input<1 || overlap_last<1 || overlap_ram<1)
            $fatal(1,"R3 coverage incomplete clear=%0d reset=%0d rejects=%0d checks=%0d begin=%0d input=%0d last=%0d ram=%0d",late_clear,late_reset,errors,checks,overlap_begin,overlap_input,overlap_last,overlap_ram);
        $display("R3_BOUNDARY PASS late_clear=%0d late_reset=%0d expected_rejections=%0d fresh_checks=%0d overlap_begin=%0d overlap_input=%0d overlap_last=%0d overlap_ram=%0d loads=%0d returns=%0d",late_clear,late_reset,errors,checks,overlap_begin,overlap_input,overlap_last,overlap_ram,loads,returns);
        $finish;
    end
    initial begin #10000000;$fatal(1,"R3 boundary timeout");end
endmodule

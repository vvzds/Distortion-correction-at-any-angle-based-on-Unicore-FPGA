`timescale 1ns/1ps
// C50 integration boundary test: real host/param_mgr/writer, injected core pixels.
// It does not claim to test core mapping, physical DDR, or HDMI.
module advanced3_c50_write_tb;
    reg clk=0; always #4 clk=~clk;
    reg rst_n=0, rx=1, busy=0;
    reg v=0,sop=0,eop=0,sof=0,eof=0;
    reg [15:0] pixel=0;
    wire req,commit,slot_req;
    wire [23:0] addr;
    wire [31:0] data;
    reg grant=0;
    integer f,n,cycles=0,frame_start_cycle=0,last_progress_cycle=0;
    integer commits=0,word_index=0,checks=0,errors=0,credit_pauses=0;
    integer aligned=0,uart_updates=0;
    reg held=0; reg [23:0] held_addr; reg [31:0] held_data;
    reg [15:0] expected_table [0:11];
    integer t, rr,gg,bb;
    reg [15:0] base_pixel;
    corr_top #(.CLK_FREQ(12500000),.ADAPTIVE_GAMMA(1)) dut(
        .clk(clk),.rst_n(rst_n),.i_uart_rx(rx),.o_uart_tx(),
        .i_frame_wcnt(2'd0),.i_frame_update(1'b0),
        .o_corr_src_hold_req(),.i_corr_src_hold_gnt(1'b0),
        .i_corr_src_slot(2'd0),.o_corr_src_rel(),
        .o_corr_rd_req(),.o_corr_rd_addr(),.o_corr_rd_len(),
        .i_corr_rd_gnt(1'b0),.i_corr_rd_vld(1'b0),
        .i_corr_rd_data(256'd0),.i_corr_rd_last(1'b0),
        .o_corr_wr_slot_req(slot_req),.i_corr_wr_slot_gnt(1'b1),
        .i_corr_wr_slot(3'd4),.o_corr_wr_commit(commit),
        .o_corr_wr_req(req),.o_corr_wr_addr(addr),.o_corr_wr_data(data),
        .i_corr_wr_gnt(grant),.i_corr_pub_pulse(commit));

    function [15:0] source_pixel;
        input integer frame, index;
        begin source_pixel=(frame==2) ? (16'hffff ^ (index & 3)) : (16'h2104 | (index & 3)); end
    endfunction
    function [15:0] expected_pixel;
        input integer frame,index;
        begin
            expected_pixel=expected_table[frame*4+(index&3)];
        end
    endfunction
    task uart_byte;
        input [7:0] b; integer k;
        begin
            @(negedge clk);rx=0;repeat(108) @(negedge clk);
            for(k=0;k<8;k=k+1) begin rx=b[k];repeat(108) @(negedge clk);end
            rx=1;repeat(108) @(negedge clk);
        end
    endtask
    task uart_gamma;
        input on;
        begin
            uart_byte(8'haa);uart_byte(8'h55);uart_byte(8'h04);uart_byte(8'h04);
            uart_byte({7'd0,on});uart_byte(0);uart_byte(0);uart_byte(0);uart_byte({7'd0,on});
            repeat(30) @(negedge clk);
        end
    endtask
    task check_fail;
        input [255:0] reason;
        begin
            if(errors<8) $display("FAIL %0s frame=%0d word=%0d cycle=%0d",reason,commits,word_index,cycles);
            errors=errors+1;
        end
    endtask
    always @(negedge clk) begin
        cycles=cycles+1;
        grant=rst_n && (cycles-frame_start_cycle>=6000) && (cycles%257>=64);
    end
    always @(posedge clk) if(rst_n) begin
        if(held && (!req || addr!==held_addr || data!==held_data)) check_fail("stalled request changed");
        held=req && !grant;held_addr=addr;held_data=data;
        if(dut.w_g_pix_vld) begin
            if(dut.r_sof!==(aligned%2073600==0) || dut.r_eof!==(aligned%2073600==2073599) ||
               dut.r_sop!==(aligned%1920==0) || dut.r_eop!==(aligned%1920==1919)) check_fail("pixel marker alignment");
            aligned=aligned+1;
        end
        if(req && grant) begin
            if(addr!==(24'h400000+word_index) ||
               data!=={expected_pixel(commits,word_index*2+1),expected_pixel(commits,word_index*2)}) check_fail("write data/address mismatch");
            word_index=word_index+1;checks=checks+1;
        end
        if(commit) begin
            if(word_index!=1036800) check_fail("incomplete frame commit");
            word_index=0;commits=commits+1;
        end
        if(dut.u_wr_if.fault) $fatal(1,"FAIL writer fault");
    end
    initial begin
        for(t=0;t<12;t=t+1) begin
            base_pixel=source_pixel(t/4,t%4);
            if(t/4==1) begin
                rr={base_pixel[15:11],base_pixel[15:13]};
                gg={base_pixel[10:5],base_pixel[10:9]};
                bb={base_pixel[4:0],base_pixel[4:2]};
                rr=$rtoi(255.0*((rr/255.0)**0.8)+0.5)/8;
                gg=$rtoi(255.0*((gg/255.0)**0.8)+0.5)/4;
                bb=$rtoi(255.0*((bb/255.0)**0.8)+0.5)/8;
                expected_table[t]=(rr<<11)|(gg<<5)|bb;
            end else expected_table[t]=base_pixel;
        end
        $display("GOLDEN_PRECOMPUTED 12 RGB565 entries");
        $fflush;
    end
    initial begin
        #150000000; $fatal(1,"FAIL timeout");
    end
    initial begin
        force dut.w_upd_pix_vld=v;force dut.w_upd_pix=pixel;
        force dut.w_core_sop=sop;force dut.w_core_eop=eop;
        force dut.w_core_sof=sof;force dut.w_core_eof=eof;
        force dut.w_frame_busy=busy;
        repeat(4) @(negedge clk);rst_n=1;
        repeat(8) @(negedge clk);
        for(f=0;f<3;f=f+1) begin
            busy=1;frame_start_cycle=cycles;
            last_progress_cycle=cycles;
            $display("FRAME_START frame=%0d cycle=%0d gamma_en=%0b curve=%0d",f,cycles,dut.w_gamma_en,dut.G_ADAPTIVE.u_gamma.pending_curve);
            $fflush;
            fork
                begin
                    repeat(120) @(negedge clk);
                    if(f<2) begin
                        uart_gamma(f==0);
                        if(dut.w_gamma_en!==(f==1)) check_fail("UART changed active busy frame");
                        uart_updates=uart_updates+1;
                    end
                end
                begin
                    n=0;
                    while(n<2073600) begin
                        @(negedge clk);
                        v=dut.w_sink_ready && (cycles%17!=0);
                        if(!dut.w_sink_ready) credit_pauses=credit_pauses+1;
                        pixel=source_pixel(f,n);
                        sop=v && (n%1920==0);eop=v && (n%1920==1919);
                        sof=v && (n==0);eof=v && (n==2073599);
                        if(v) begin
                            n=n+1;
                            last_progress_cycle=cycles;
                            if(n%230400==0) begin
                                $display("FRAME_PROGRESS frame=%0d pixels=%0d words=%0d credit_pauses=%0d cycle=%0d",f,n,checks,credit_pauses,cycles);
                                $fflush;
                            end
                        end
                        if(cycles-last_progress_cycle>50000)
                            $fatal(1,"FAIL stalled frame=%0d pixel=%0d words=%0d credit=%0b fifo=%0d",f,n,checks,dut.w_sink_ready,dut.u_wr_if.fifo_count);
                    end
                    @(negedge clk);v=0;sop=0;eop=0;sof=0;eof=0;
                end
            join
            wait(commits==f+1);
            @(negedge clk);busy=0;
            repeat(64) @(negedge clk);
            if(dut.w_gamma_en!==(f==0)) check_fail("UART mode not applied at idle");
            $display("FRAME=%0d COMMIT=%0d WORDS=%0d CREDIT_PAUSES=%0d",f,commits,checks,credit_pauses);
            $fflush;
        end
        if(checks!=3110400 || aligned!=6220800 || commits!=3 || dut.pub_count!=3 || credit_pauses==0 || uart_updates!=2)
            check_fail("final counters");
        $display("WRITE_WORDS=%0d PIXELS=%0d COMMITS=%0d UART_UPDATES=%0d CREDIT_PAUSES=%0d err=%0d",checks,aligned,commits,uart_updates,credit_pauses,errors);
        if(errors==0) $display("=== ALL TESTS PASSED (err=0) ===");
        else $fatal(1,"FAIL err=%0d",errors);
        $finish;
    end
endmodule

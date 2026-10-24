`timescale 1ns/1ps
// 核边界注入：使用真实corr_top/param_mgr/rect_wr_if，核心输出仅由本TB驱动。
// 本测试证明Gamma到写回的组合边界，不是核心或DDR整机验收。
module gamma_write_path_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0;
    reg v=0,sop=0,eop=0,sof=0,eof=0;
    reg [15:0] pixel=0;
    wire req,commit,slot_req;
    wire [23:0] addr;
    wire [31:0] data;
    integer n,f,word_index=0,commits=0,err=0,checks=0,wait_cycles=0;
    reg [15:0] expected_pixel;
    corr_top #(.ADAPTIVE_GAMMA(1)) dut(
        .clk(clk),.rst_n(rst_n),.i_uart_rx(1'b1),.o_uart_tx(),
        .i_frame_wcnt(2'd0),.i_frame_update(1'b0),
        .o_corr_src_hold_req(),.i_corr_src_hold_gnt(1'b0),
        .i_corr_src_slot(2'd0),.o_corr_src_rel(),
        .o_corr_rd_req(),.o_corr_rd_addr(),.o_corr_rd_len(),
        .i_corr_rd_gnt(1'b0),.i_corr_rd_vld(1'b0),
        .i_corr_rd_data(256'd0),.i_corr_rd_last(1'b0),
        .o_corr_wr_slot_req(slot_req),.i_corr_wr_slot_gnt(1'b1),
        .i_corr_wr_slot(3'd4),.o_corr_wr_commit(commit),
        .o_corr_wr_req(req),.o_corr_wr_addr(addr),.o_corr_wr_data(data),
        .i_corr_wr_gnt(1'b1),.i_corr_pub_pulse(commit));
    function [15:0] golden;
        input integer frame;
        integer rr,gg,bb;
        real exponent;
        begin
            exponent=(frame==0)?1.0:0.8;
            rr=$rtoi(255.0*((33.0/255.0)**exponent)+0.5)/8;
            gg=$rtoi(255.0*((32.0/255.0)**exponent)+0.5)/4;
            bb=rr;
            golden=(rr<<11)|(gg<<5)|bb;
        end
    endfunction
    always @(posedge clk) if(rst_n) begin
        if(req) begin
            expected_pixel=golden(commits);
            if(addr!==(24'h400000+word_index) ||
               data!=={expected_pixel,expected_pixel}) begin
                if(err<5) $display("FAIL write frame=%0d index=%0d data=%h",commits,word_index,data);
                err=err+1;
            end
            word_index=word_index+1;checks=checks+1;
        end
        if(commit) begin
            if(word_index!=1036800)err=err+1;
            word_index=0;commits=commits+1;
        end
        if(dut.u_wr_if.fault) begin $display("FAIL writer fault");$finish;end
    end
    initial begin
        force dut.w_upd_pix_vld=v;
        force dut.w_upd_pix=pixel;
        force dut.w_core_sop=sop;force dut.w_core_eop=eop;
        force dut.w_core_sof=sof;force dut.w_core_eof=eof;
        force dut.w_gamma_en=1'b1;
        repeat(3) @(negedge clk);rst_n=1;
        for(f=0;f<2;f=f+1) begin
            for(n=0;n<2073600;n=n+1) begin
                @(negedge clk);v=1;pixel=16'h2104;
                sop=(n%1920==0);eop=(n%1920==1919);
                sof=(n==0);eof=(n==2073599);
                @(negedge clk);v=0;sop=0;eop=0;sof=0;eof=0;
            end
            wait_cycles=0;
            while(commits<f+1 && wait_cycles<100) begin
                @(negedge clk);wait_cycles=wait_cycles+1;
            end
            if(commits!=f+1)err=err+1;
        end
        repeat(10) @(negedge clk);
        if(checks!=2073600 || dut.pub_count!=2)err=err+1;
        $display("WRITE_WORDS=%0d COMMITS=%0d err=%0d",checks,commits,err);
        if(err==0)$display("=== ALL TESTS PASSED (err=0) ===");
        else $display("FAIL err=%0d",err);
        $finish;
    end
endmodule

`timescale 1ns/1ps
// Bounded C50 host smoke: auto-Gamma, marker alignment and writer packing.
module advanced3_c50_smoke_tb;
    reg clk=0; always #4 clk=~clk;
    reg rst_n=0,v=0,sop=0,eop=0,sof=0,eof=0;
    reg [15:0] pixel=16'h2104;
    wire req,commit;
    wire [23:0] addr;
    wire [31:0] data;
    integer n,words=0,pixels=0,errors=0;
    reg [15:0] expected;
    integer r,g,b;
    corr_top #(.ADAPTIVE_GAMMA(1)) dut(
        .clk(clk),.rst_n(rst_n),.i_uart_rx(1'b1),.o_uart_tx(),
        .i_frame_wcnt(2'd0),.i_frame_update(1'b0),
        .o_corr_src_hold_req(),.i_corr_src_hold_gnt(1'b0),
        .i_corr_src_slot(2'd0),.o_corr_src_rel(),
        .o_corr_rd_req(),.o_corr_rd_addr(),.o_corr_rd_len(),
        .i_corr_rd_gnt(1'b0),.i_corr_rd_vld(1'b0),
        .i_corr_rd_data(256'd0),.i_corr_rd_last(1'b0),
        .o_corr_wr_slot_req(),.i_corr_wr_slot_gnt(1'b1),
        .i_corr_wr_slot(3'd4),.o_corr_wr_commit(commit),
        .o_corr_wr_req(req),.o_corr_wr_addr(addr),.o_corr_wr_data(data),
        .i_corr_wr_gnt(1'b1),.i_corr_pub_pulse(commit));
    always @(posedge clk) if(rst_n) begin
        if(dut.w_g_pix_vld) begin
            if(dut.r_sof!==(pixels==0) || dut.r_sop!==(pixels==0) || dut.r_eof || dut.r_eop) errors=errors+1;
            pixels=pixels+1;
        end
        if(req) begin
            if(addr!==(24'h400000+words) || data!=={expected,expected}) begin
                if(errors<5) $display("FAIL write word=%0d got=%h expected=%h",words,data,{expected,expected});
                errors=errors+1;
            end
            words=words+1;
        end
        if(dut.u_wr_if.fault || commit) errors=errors+1;
    end
    initial begin
        force dut.w_upd_pix_vld=v;force dut.w_upd_pix=pixel;
        force dut.w_core_sop=sop;force dut.w_core_eop=eop;
        force dut.w_core_sof=sof;force dut.w_core_eof=eof;
        force dut.w_gamma_en=1'b1;
        r=$rtoi(255.0*((33.0/255.0)**0.8)+0.5)/8;
        g=$rtoi(255.0*((32.0/255.0)**0.8)+0.5)/4;
        b=r;expected=(r<<11)|(g<<5)|b;
        repeat(4) @(negedge clk);rst_n=1;
        force dut.G_ADAPTIVE.u_gamma.pending_curve=3'd1;
        for(n=0;n<128;n=n+1) begin
            @(negedge clk);v=1;sop=(n==0);sof=(n==0);
            @(negedge clk);v=0;sop=0;sof=0;
        end
        repeat(16) @(negedge clk);
        if(words!=64 || pixels!=128 || !dut.u_wr_if.input_open || !dut.w_sink_ready) errors=errors+1;
        $display("WORDS=%0d PIXELS=%0d ERRORS=%0d",words,pixels,errors);
        if(errors==0) $display("=== ALL TESTS PASSED (err=0) ===");
        else $display("FAIL errors=%0d",errors);
        $finish;
    end
endmodule

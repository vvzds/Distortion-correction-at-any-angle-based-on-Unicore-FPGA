`timescale 1ns/1ps

module frame_start_tb;
    reg clk=0, rst_n=0, start=0;
    always #4 clk=~clk;
    reg signed [31:0] fx=32'sd65536000, fy=32'sd65536000;
    reg signed [31:0] a22=32'sh00010000;
    wire busy, hold_req;
    integer errors=0;

    undistort_core #(.SIM_MODE(1)) dut (
        .clk(clk), .rst_n(rst_n), .i_sink_ready(1'b1),
        .i_fx(fx), .i_fy(fy),
        .i_cx(32'sd62914560), .i_cy(32'sd35389440),
        .i_k1(32'sd0), .i_k2(32'sd0), .i_p1(32'sd0), .i_p2(32'sd0),
        .i_aff_a11(32'sh00010000), .i_aff_a12(32'sd0),
        .i_aff_a21(32'sd0), .i_aff_a22(a22),
        .i_aff_tx(32'sd0), .i_aff_ty(32'sd0), .i_aff_en(1'b1),
        .i_frame_start(start), .o_frame_busy(busy),
        .o_corr_src_hold_req(hold_req), .i_corr_src_hold_gnt(1'b0),
        .i_corr_src_slot(2'd0), .i_corr_rd_gnt(1'b0),
        .i_corr_rd_vld(1'b0), .i_corr_rd_data(256'd0),
        .i_corr_rd_last(1'b0)
    );

    task check;
        input condition;
        input [255:0] label;
        begin
            if (condition !== 1'b1) begin
                $display("FAIL: %0s", label);
                errors=errors+1;
            end
        end
    endtask

    initial begin
        repeat (2) @(negedge clk);
        rst_n=1;
        start=1;
        @(posedge clk); #1;
        check(dut.start_valid_q && dut.state==0 && !busy,
              "start accepted before hold");
        check(dut.fx==32'sd65536000 && dut.a22==32'sh00010000,
              "parameters captured on start");

        @(negedge clk);
        start=0;
        fx=0;
        a22=32'sh00030000;
        @(posedge clk); #1;
        check(dut.state==1 && busy && hold_req,
              "registered start enters hold");
        check(dut.fx==32'sd65536000 && dut.a22==32'sh00010000,
              "changed inputs cannot enter active frame");
        repeat (3) begin
            @(posedge clk); #1;
            check(dut.state==1 && dut.fx==32'sd65536000 &&
                  dut.a22==32'sh00010000, "hold uses captured parameters");
        end

        @(negedge clk);
        rst_n=0;
        start=0;
        @(negedge clk);
        rst_n=1;
        start=1;
        @(posedge clk); #1;
        check(!dut.start_valid_q && !busy, "invalid parameters rejected");
        @(negedge clk); start=0;
        @(posedge clk); #1;
        check(dut.state==0 && !hold_req, "invalid start never enters hold");

        if (errors==0) $display("C63 FRAME START PASS");
        else $fatal(1, "C63 FRAME START FAIL errors=%0d", errors);
        $finish;
    end
endmodule

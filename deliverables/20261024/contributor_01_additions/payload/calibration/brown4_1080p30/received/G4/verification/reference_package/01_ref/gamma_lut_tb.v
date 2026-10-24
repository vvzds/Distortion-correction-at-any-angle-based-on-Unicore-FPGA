//============================================================================
// gamma_lut_tb.v —— gamma_lut self-checking testbench (Task #2)
//----------------------------------------------------------------------------
// Method   : ModelSim batch self-check (vsim -c + do script), no waveform.
//            DUT is a strict 1-cycle pipeline: drive 1 pixel per clock and
//            compare the output in the SAME task call (output for that input
//            appears at the next posedge).
// Observed : o_pix_vld, o_pix (mapped or bypassed RGB565).
// Expected :
//   G0 reset defaults: o_pix_vld=0
//   G1 bypass (en=0): random pixels pass through unchanged
//   G2 identity LUT + en=1: output == input (lossless round-trip property,
//      checked directly against input, independent of gold() formula)
//   G3 asymmetric LUT (R=i, G=255-i, B=i^0xA5) + en=1: 128 random pixels
//   G4 boundary pixels 0x0000/0xFFFF/0xF800/0x07E0/0x001F with G3 LUT
//   G5 enable toggled every beat: per-beat mode select, no residue
//   G6 irregular i_pix_vld gaps: vld passes through, data only checked when vld=1
//============================================================================
`timescale 1ns/1ps

module gamma_lut_tb;

    reg         clk = 1'b0;
    reg         rst_n;
    reg         i_pix_vld;
    reg  [15:0] i_pix;
    reg         i_gamma_en;
    reg  [6143:0] i_gamma_lut;
    wire        o_pix_vld;
    wire [15:0] o_pix;

    gamma_lut dut (
        .clk(clk), .rst_n(rst_n),
        .i_pix_vld(i_pix_vld), .i_pix(i_pix),
        .o_pix_vld(o_pix_vld), .o_pix(o_pix),
        .i_gamma_en(i_gamma_en), .i_gamma_lut(i_gamma_lut)
    );

    always #4 clk = ~clk;    // 125 MHz

    //----------------------------------------------------------
    // Watchdog
    //----------------------------------------------------------
    initial begin
        #1_000_000;
        $display("[%0t] FAIL: watchdog timeout", $time);
        $finish;
    end

    //----------------------------------------------------------
    // Error counter
    //----------------------------------------------------------
    integer err = 0;

    //----------------------------------------------------------
    // LUT model (mirror of what is driven onto the flat bus)
    //----------------------------------------------------------
    reg [7:0] lut3 [0:2][0:255];

    task build_flat;
        integer c, i;
        begin
            for (i = 0; i < 256; i = i + 1) begin
                i_gamma_lut[8*i        +: 8] = lut3[0][i];   // R
                i_gamma_lut[2048+8*i   +: 8] = lut3[1][i];   // G
                i_gamma_lut[4096+8*i   +: 8] = lut3[2][i];   // B
            end
        end
    endtask

    // Golden reference (deliberately written from the spec, shares no
    // expression with the RTL beyond the documented bit-replication rule)
    function [15:0] gold(input [15:0] p, input en);
        reg [7:0] r8, g8, b8;
        reg [7:0] lr, lg, lb;   // Verilog-2001 cannot part-select an array
        begin                   // element directly -> stage to a plain vector
            if (!en) gold = p;
            else begin
                r8 = {p[15:11], p[15:13]};
                g8 = {p[10:5],  p[10:9]};
                b8 = {p[4:0],   p[4:2]};
                lr = lut3[0][r8];
                lg = lut3[1][g8];
                lb = lut3[2][b8];
                gold = {lr[7:3], lg[7:2], lb[7:3]};
            end
        end
    endfunction

    //----------------------------------------------------------
    // Drive 1 beat and check the output produced for THIS input.
    // en/vld are sampled by the DUT on the next posedge together with p.
    //----------------------------------------------------------
    task drive_check(input [15:0] p, input en, input vld);
        reg [15:0] exp;
        begin
            i_pix     <= p;
            i_gamma_en <= en;
            i_pix_vld <= vld;
            @(posedge clk);
            #1;   // let the DUT's same-edge NBA updates land before reading
            if (o_pix_vld !== vld) begin
                $display("[%0t] FAIL: vld got=%b exp=%b (p=%h en=%b)", $time, o_pix_vld, vld, p, en);
                err = err + 1;
            end else if (vld) begin
                exp = gold(p, en);
                if (o_pix !== exp) begin
                    $display("[%0t] FAIL: pix p=%h en=%b got=%h exp=%h", $time, p, en, o_pix, exp);
                    err = err + 1;
                end
            end
        end
    endtask

    //----------------------------------------------------------
    // Main sequence
    //----------------------------------------------------------
    integer k;
    reg [15:0] rp;

    initial begin
        $display("==== gamma_lut_tb self-check simulation start ====");

        // ---- G0 reset ----
        rst_n = 1'b0;
        i_pix_vld = 1'b0; i_pix = 16'h0; i_gamma_en = 1'b0; i_gamma_lut = 6144'h0;
        repeat (10) @(posedge clk);
        if (o_pix_vld !== 1'b0) begin
            $display("[%0t] FAIL: G0 o_pix_vld not 0 after reset", $time);
            err = err + 1;
        end
        rst_n = 1'b1;
        @(posedge clk);
        $display("G0 reset defaults: done");

        // ---- G1 bypass (en=0): random pixels pass through ----
        for (k = 0; k < 64; k = k + 1) begin
            rp = $random;
            drive_check(rp, 1'b0, 1'b1);
        end
        $display("G1 bypass pass-through: done");

        // ---- G2 identity LUT + en=1: output == input (property check) ----
        for (k = 0; k < 256; k = k + 1) begin
            lut3[0][k] = k[7:0];
            lut3[1][k] = k[7:0];
            lut3[2][k] = k[7:0];
        end
        build_flat;
        for (k = 0; k < 64; k = k + 1) begin
            rp = $random;
            drive_check(rp, 1'b1, 1'b1);
            if (o_pix !== rp) begin
                $display("[%0t] FAIL: G2 identity LUT not lossless p=%h got=%h", $time, rp, o_pix);
                err = err + 1;
            end
        end
        $display("G2 identity LUT lossless round-trip: done");

        // ---- G3 asymmetric LUT: R=i, G=255-i, B=i^0xA5 ----
        for (k = 0; k < 256; k = k + 1) begin
            lut3[0][k] = k[7:0];
            lut3[1][k] = 8'hFF - k[7:0];
            lut3[2][k] = k[7:0] ^ 8'hA5;
        end
        build_flat;
        for (k = 0; k < 128; k = k + 1) begin
            rp = $random;
            drive_check(rp, 1'b1, 1'b1);
        end
        $display("G3 asymmetric 3-channel LUT mapping: done");

        // ---- G4 boundary pixels with G3 LUT ----
        drive_check(16'h0000, 1'b1, 1'b1);
        drive_check(16'hFFFF, 1'b1, 1'b1);
        drive_check(16'hF800, 1'b1, 1'b1);   // pure R max
        drive_check(16'h07E0, 1'b1, 1'b1);   // pure G max
        drive_check(16'h001F, 1'b1, 1'b1);   // pure B max
        $display("G4 boundary pixels: done");

        // ---- G5 enable toggled every beat ----
        for (k = 0; k < 32; k = k + 1) begin
            rp = $random;
            drive_check(rp, k[0], 1'b1);     // en alternates 0/1/0/1...
        end
        $display("G5 per-beat enable toggle: done");

        // ---- G6 irregular vld gaps ----
        for (k = 0; k < 64; k = k + 1) begin
            rp = $random;
            drive_check(rp, 1'b1, ($random % 3) == 0);
        end
        $display("G6 irregular vld gaps: done");

        // ---- Summary ----
        if (err == 0) $display("=== ALL TESTS PASSED (err=0) ===");
        else         $display("=== TEST FAILED: err=%0d ===", err);
        $finish;
    end

endmodule

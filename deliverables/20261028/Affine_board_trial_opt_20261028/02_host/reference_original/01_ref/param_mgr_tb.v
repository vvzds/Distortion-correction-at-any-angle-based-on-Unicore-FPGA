//============================================================================
// param_mgr_tb.v —— param_mgr self-checking testbench (Task #1)
//----------------------------------------------------------------------------
// Method    : ModelSim batch self-check (vsim -c + do script), no waveform
//             inspection needed. Step-by-step expected-value compare, error
//             counter, final PASS/FAIL verdict printed.
// Observed  : o_param_updated (swap pulse), all parameter outputs,
//             o_params_valid (D06 gating, V1.2), o_uart_tx (cmd0x05 readback).
// Expected  :
//   S0  reset defaults: all-zero outputs, no updated pulse, params_valid=0
//   S1  cmd0x01 (T3 legal set) while i_rect_busy=1: no updated, params
//       unchanged, params_valid stays 0
//   S2  busy=0: exactly one updated pulse, 8 Q16.16 params correct (T3
//       acceptance values), params_valid=1
//   S3  LEGACY 24-byte cmd0x02 frame (V1.1 format): REJECTED by len compare
//       (V1.2 expects 25), no pulse, no shadow effect, params_valid unchanged
//   S4  NEW 25-byte cmd0x02 (tail enable byte=0x00) while busy=1: no updated
//   S5  busy=0: updated, 6 affine params live, a11 bit-exact 0x0001_0000
//       (no enable-carrier pollution), o_aff_en=0, params_valid=1
//   S6  25-byte 0x02, tail enable byte=0x01: o_aff_en=1 AND a11 unchanged
//       (G01 core regression: enable + identity coefficient now coexist --
//       the combination T5 pure-translation needs, impossible under V1.1)
//   S6b 25-byte 0x02, tail enable byte=0x02: o_aff_en=0 (read side samples
//       bit0 only, reserved bits ignored, V1.2 §5.3)
//   S7  three cmd0x03 frames (R/G/B) while busy=1: no updated (shadow
//       aggregation), params_valid stays 1
//   S8  busy=0: single updated pulse, all 3 LUT channels live (spot check)
//   S9  cmd0x04 mode word bit0=1: updated, o_gamma_en=1
//   S10 frame with bad checksum: dropped, params kept, params_valid=1
//   S11 cmd0x05: TX frame AA 55 05 04 + status LE + checksum verified
//       (TX_GAP: reply start bit >= 2 bits after downlink frame end)
//   S12 cmd0x04 (bit0=0) while busy=1: no updated; busy=0: updated, o_gamma_en=0
//   S13a cmd0x01 with fx=0x007F_FFFF (1 LSB below G02 lower bound 128.0):
//       params still go live, but params_valid=0 (out-of-range group)
//   S13b cmd0x01 with fx=0x0080_0000 (128.0, G02 boundary inclusive):
//       params_valid=1
//   S14 cmd0x01 restore T3 fx=1000.0: params_valid=1, o_fx restored
//   Total expected o_param_updated pulses: 10
//
// Bit-reuse audit (V1.2 rework item "all-command sweep", conclusion):
//   0x01: 32B payload purely param data, no embedded flag -- clean.
//   0x02: enable moved to dedicated tail byte bit0 by this rework -- clean.
//   0x03: len field reused as channel number -- frozen V1.2 revision, by design.
//   0x04: mode word is bit-semantic by definition, read side samples bit0 only.
//   0x05: len fixed 0. No protocol-level mutual exclusion remains after G01.
//
// Speedup   : DUT instantiated with CLK_FREQ=12.5MHz (1/10 of real 125MHz),
//             DIV=108 -> equivalent baud x10, time axis scaled, logic identical.
//============================================================================
`timescale 1ns/1ps

module param_mgr_tb;

    localparam integer CLK_FREQ_TB = 12_500_000;              // simulated freq
    localparam integer DIV = CLK_FREQ_TB / 115_200;           // = 108 clk/bit
    localparam [31:0] STATUS_VAL = 32'hA5A5_1234;

    reg         clk = 1'b0;
    reg         rst_n;
    reg         i_uart_rx = 1'b1;
    reg         i_rect_busy = 1'b1;
    wire        o_uart_tx, o_param_updated;
    wire signed [31:0] o_fx, o_fy, o_cx, o_cy, o_k1, o_k2, o_p1, o_p2;
    wire signed [31:0] o_a11, o_a12, o_a21, o_a22, o_tx, o_ty;
    wire        o_aff_en, o_gamma_en;
    wire        o_params_valid;
    wire [6143:0] o_gamma_lut;

    param_mgr #(
        .CLK_FREQ (CLK_FREQ_TB),
        .BAUD_RATE(115_200)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .i_uart_rx(i_uart_rx), .o_uart_tx(o_uart_tx),
        .i_rect_busy(i_rect_busy), .o_param_updated(o_param_updated),
        .o_fx(o_fx), .o_fy(o_fy), .o_cx(o_cx), .o_cy(o_cy),
        .o_k1(o_k1), .o_k2(o_k2), .o_p1(o_p1), .o_p2(o_p2),
        .o_aff_a11(o_a11), .o_aff_a12(o_a12), .o_aff_a21(o_a21),
        .o_aff_a22(o_a22), .o_aff_tx(o_tx), .o_aff_ty(o_ty),
        .o_aff_en(o_aff_en), .o_params_valid(o_params_valid),
        .o_gamma_en(o_gamma_en), .o_gamma_lut(o_gamma_lut),
        .o_hist_rd_en(), .o_hist_ch(), .i_hist_count(24'd0),
        .i_status(STATUS_VAL)
    );

    always #4 clk = ~clk;    // 125 MHz

    //----------------------------------------------------------
    // Watchdog (independent process)
    //----------------------------------------------------------
    initial begin
        #60_000_000;
        $display("[%0t] FAIL: watchdog timeout", $time);
        $finish;
    end

    //----------------------------------------------------------
    // Error counter / updated monitor
    //----------------------------------------------------------
    integer err = 0;
    integer upd_cnt = 0;
    reg upd_d = 0;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin upd_cnt <= 0; upd_d <= 0; end
        else begin
            upd_d <= o_param_updated;
            if (o_param_updated) begin
                upd_cnt <= upd_cnt + 1;
                if (upd_d) begin
                    $display("[%0t] FAIL: o_param_updated asserted 2 cycles in a row (must be single-cycle)", $time);
                    err = err + 1;
                end
            end
        end
    end

    //----------------------------------------------------------
    // UART low-level tasks
    //----------------------------------------------------------
    // Send 1 byte: start(0) + 8 data bits (LSB first) + stop(1), DIV clks/bit
    task uart_send_byte(input [7:0] b);
        integer k;
        begin
            i_uart_rx <= 1'b0;                 // start bit
            repeat (DIV) @(posedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                i_uart_rx <= b[k];
                repeat (DIV) @(posedge clk);
            end
            i_uart_rx <= 1'b1;                 // stop bit
            repeat (DIV) @(posedge clk);
        end
    endtask

    // Global frame buffer used by send_frame
    reg [7:0] frame_buf [0:255];
    integer   frame_len;

    // Send frame: AA 55 cmd len payload... checksum.
    // use_bad_chk=1 -> send inverted-ish wrong checksum on purpose
    task send_frame(input [7:0] cmd, input [7:0] len, input use_bad_chk);
        integer k;
        reg [7:0] chk;
        begin
            chk = 8'h00;
            for (k = 0; k < frame_len; k = k + 1) chk = chk + frame_buf[k];
            uart_send_byte(8'hAA);
            uart_send_byte(8'h55);
            uart_send_byte(cmd);
            uart_send_byte(len);
            for (k = 0; k < frame_len; k = k + 1) uart_send_byte(frame_buf[k]);
            if (use_bad_chk) uart_send_byte(chk ^ 8'h5A);   // deliberately bad
            else             uart_send_byte(chk);
            repeat (10) @(posedge clk);                       // inter-frame gap
        end
    endtask

    // Load a cmd0x01 payload into frame_buf: fx taken from fx_val, the other
    // seven params fixed at the T3 acceptance set (V1.2 §3.5): fy=1000.0,
    // cx=960.0, cy=540.0, k1=-0.1 (=-6554=0xFFFF_E666), k2=p1=p2=0 -- all
    // inside G02 ranges.
    task load_01_payload(input [31:0] fx_val);
        begin
            frame_buf[0]=fx_val[7:0];   frame_buf[1]=fx_val[15:8];               // fx (LE)
            frame_buf[2]=fx_val[23:16]; frame_buf[3]=fx_val[31:24];
            frame_buf[4]=8'h00; frame_buf[5]=8'h00; frame_buf[6]=8'hE8;  frame_buf[7]=8'h03;  // fy=1000.0
            frame_buf[8]=8'h00;  frame_buf[9]=8'h00;  frame_buf[10]=8'hC0; frame_buf[11]=8'h03; // cx=960.0
            frame_buf[12]=8'h00; frame_buf[13]=8'h00; frame_buf[14]=8'h1C; frame_buf[15]=8'h02; // cy=540.0
            frame_buf[16]=8'h66; frame_buf[17]=8'hE6; frame_buf[18]=8'hFF; frame_buf[19]=8'hFF; // k1=-0.1
            frame_buf[20]=8'h00; frame_buf[21]=8'h00; frame_buf[22]=8'h00; frame_buf[23]=8'h00; // k2=0
            frame_buf[24]=8'h00; frame_buf[25]=8'h00; frame_buf[26]=8'h00; frame_buf[27]=8'h00; // p1=0
            frame_buf[28]=8'h00; frame_buf[29]=8'h00; frame_buf[30]=8'h00; frame_buf[31]=8'h00; // p2=0
        end
    endtask

    // Receive 1 byte from DUT o_uart_tx: wait start edge, then 1.5 bit to the
    // CENTER of data0 (0.5 bit only lands at start-bit center -> 1-bit skew).
    task uart_rx_byte(output [7:0] b);
        integer k;
        begin
            @(negedge o_uart_tx);
            repeat (DIV + DIV/2) @(posedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                b[k] = o_uart_tx;
                repeat (DIV) @(posedge clk);
            end
        end
    endtask

    //----------------------------------------------------------
    // Compare / wait tasks
    //----------------------------------------------------------
    task compare32(input [127:0] name, input [31:0] got, input [31:0] exp);
        begin
            if (got !== exp) begin
                $display("[%0t] FAIL: %0s got=%h exp=%h", $time, name, got, exp);
                err = err + 1;
            end
        end
    endtask
    task compare8(input [127:0] name, input [7:0] got, input [7:0] exp);
        begin
            if (got !== exp) begin
                $display("[%0t] FAIL: %0s got=%h exp=%h", $time, name, got, exp);
                err = err + 1;
            end
        end
    endtask

    // Wait until updated-pulse counter increases beyond cnt0 (recorded BEFORE
    // the event that triggers the swap). Covers the case where the swap pulse
    // fires while the UART frame is still being sent.
    task wait_upd_inc(input integer cnt0, input integer max_clks);
        integer n;
        begin
            for (n = 0; n < max_clks; n = n + 1) begin
                @(posedge clk);
                if (upd_cnt > cnt0) disable wait_upd_inc;
            end
            $display("[%0t] FAIL: timeout waiting for o_param_updated increment (base=%0d, %0d clks)", $time, cnt0, max_clks);
            err = err + 1;
        end
    endtask

    // Confirm no updated pulse within n_clks
    task wait_no_upd(input integer n_clks);
        integer n;
        begin
            for (n = 0; n < n_clks; n = n + 1) begin
                @(posedge clk);
                if (o_param_updated) begin
                    $display("[%0t] FAIL: unexpected o_param_updated pulse", $time);
                    err = err + 1;
                    disable wait_no_upd;
                end
            end
        end
    endtask

    //----------------------------------------------------------
    // Main test sequence
    //----------------------------------------------------------
    integer k;
    integer cnt0;
    reg [7:0] rb [0:8];

    initial begin
        $display("==== param_mgr_tb self-check simulation start (DIV=%0d) ====", DIV);

        // ---- S0 reset & defaults ----
        rst_n = 1'b0;
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);
        compare32("S0 o_fx",  o_fx,  32'h0);
        compare32("S0 o_k1",  o_k1,  32'h0);
        compare32("S0 o_a11", o_a11, 32'h0);
        compare32("S0 o_aff_en",       {31'h0, o_aff_en},       32'h0);
        compare32("S0 o_gamma_en",     {31'h0, o_gamma_en},     32'h0);
        compare32("S0 o_params_valid", {31'h0, o_params_valid}, 32'h0);
        wait_no_upd(20);
        $display("S0 reset defaults: done");

        // ---- S1 cmd0x01 (T3 legal set) while busy=1: no effect ----
        i_rect_busy = 1'b1;
        load_01_payload(32'h03E8_0000);            // fx = 1000.0 (T3)
        frame_len = 32;
        send_frame(8'h01, 8'd32, 1'b0);
        wait_no_upd(300);
        compare32("S1 o_fx unchanged while busy", o_fx, 32'h0);
        compare32("S1 o_params_valid stays 0 while busy", {31'h0, o_params_valid}, 32'h0);
        $display("S1 busy hold check: done (no pulse, params not live)");

        // ---- S2 busy=0: swap & verify 8 params ----
        cnt0 = upd_cnt;
        i_rect_busy = 1'b0;
        wait_upd_inc(cnt0, 10);
        compare32("S2 o_fx",  o_fx,  32'h03E8_0000);
        compare32("S2 o_fy",  o_fy,  32'h03E8_0000);
        compare32("S2 o_cx",  o_cx,  32'h03C0_0000);
        compare32("S2 o_cy",  o_cy,  32'h021C_0000);
        compare32("S2 o_k1",  o_k1,  32'hFFFF_E666);
        compare32("S2 o_k2",  o_k2,  32'h0000_0000);
        compare32("S2 o_p1",  o_p1,  32'h0000_0000);
        compare32("S2 o_p2",  o_p2,  32'h0000_0000);
        compare32("S2 o_params_valid", {31'h0, o_params_valid}, 32'h1);
        $display("S2 distortion 8-param swap (T3 set): done");

        // ---- S3 LEGACY 24-byte 0x02 frame: must be REJECTED (V1.2 len=25) ----
        // busy stays 0 here on purpose: the ONLY reason not to swap must be
        // the len-field rejection in P_LEN (G01 regression, old hosts refused).
        frame_buf[0]=8'h00;  frame_buf[1]=8'h00;  frame_buf[2]=8'h01;  frame_buf[3]=8'h00;  // a11
        frame_buf[4]=8'h00;  frame_buf[5]=8'h80;  frame_buf[6]=8'h00;  frame_buf[7]=8'h00;  // a12
        frame_buf[8]=8'h00;  frame_buf[9]=8'h00;  frame_buf[10]=8'hFF; frame_buf[11]=8'hFF; // a21
        frame_buf[12]=8'h00; frame_buf[13]=8'h80; frame_buf[14]=8'h01; frame_buf[15]=8'h00; // a22
        frame_buf[16]=8'h00; frame_buf[17]=8'h00; frame_buf[18]=8'h64; frame_buf[19]=8'h00; // tx
        frame_buf[20]=8'h00; frame_buf[21]=8'hC0; frame_buf[22]=8'hFF; frame_buf[23]=8'hFF; // ty
        frame_len = 24;
        send_frame(8'h02, 8'd24, 1'b0);                       // legacy len=24
        wait_no_upd(300);
        compare32("S3 o_a11 unchanged (legacy frame rejected)", o_a11, 32'h0);
        compare32("S3 o_aff_en unchanged", {31'h0, o_aff_en}, 32'h0);
        compare32("S3 o_params_valid unchanged", {31'h0, o_params_valid}, 32'h1);
        $display("S3 legacy 24-byte 0x02 frame rejected: done");

        // ---- S4 NEW 25-byte 0x02 (tail enable byte=0x00) while busy=1 ----
        i_rect_busy = 1'b1;
        frame_buf[24] = 8'h00;                                // tail enable byte, bit0=0
        frame_len = 25;
        send_frame(8'h02, 8'd25, 1'b0);
        wait_no_upd(300);
        compare32("S4 o_a11 held while busy", o_a11, 32'h0);
        $display("S4 busy hold check: done");

        // ---- S5 busy=0: swap & verify affine (enable=0, a11 unpolluted) ----
        cnt0 = upd_cnt;
        i_rect_busy = 1'b0;
        wait_upd_inc(cnt0, 10);
        compare32("S5 o_a11", o_a11, 32'h0001_0000);   // bit-exact, no bit7 carrier pollution
        compare32("S5 o_a12", o_a12, 32'h0000_8000);
        compare32("S5 o_a21", o_a21, 32'hFFFF_0000);
        compare32("S5 o_a22", o_a22, 32'h0001_8000);
        compare32("S5 o_tx",  o_tx,  32'h0064_0000);
        compare32("S5 o_ty",  o_ty,  32'hFFFF_C000);
        compare32("S5 o_aff_en", {31'h0, o_aff_en}, 32'h0);
        compare32("S5 o_params_valid", {31'h0, o_params_valid}, 32'h1);
        $display("S5 affine 6-param swap (disabled, clean a11): done");

        // ---- S6 tail enable byte=0x01: o_aff_en=1 AND a11 unchanged ----
        // G01 core regression: under V1.1 the enable lived in a11 LSB bit7, so
        // enable=1 forced a11 low byte >= 0x80 -- identity a11=0x0001_0000 and
        // enable=1 could never coexist (T5 pure-translation undeliverable).
        frame_buf[24] = 8'h01;                                // bit0=1: affine enabled
        cnt0 = upd_cnt;                                       // swap fires DURING send (busy=0)
        send_frame(8'h02, 8'd25, 1'b0);
        wait_upd_inc(cnt0, 100);
        compare32("S6 o_aff_en", {31'h0, o_aff_en}, 32'h1);
        compare32("S6 o_a11 unchanged with en=1", o_a11, 32'h0001_0000);
        compare32("S6 o_params_valid", {31'h0, o_params_valid}, 32'h1);
        $display("S6 affine enable + identity a11 coexist (G01 fixed): done");

        // ---- S6b tail enable byte=0x02: reserved bits ignored, bit0=0 ----
        frame_buf[24] = 8'h02;                                // bit1=1 (reserved), bit0=0
        cnt0 = upd_cnt;
        send_frame(8'h02, 8'd25, 1'b0);
        wait_upd_inc(cnt0, 100);
        compare32("S6b o_aff_en", {31'h0, o_aff_en}, 32'h0);
        compare32("S6b o_a11 unchanged", o_a11, 32'h0001_0000);
        $display("S6b reserved bits ignored (bit0 only): done");

        // ---- S7 three gamma frames (R/G/B) while busy=1: shadow aggregation ----
        i_rect_busy = 1'b1;
        // R channel: lut[i] = i
        for (k = 0; k < 256; k = k + 1) frame_buf[k] = k[7:0];
        frame_len = 256;
        send_frame(8'h03, 8'd0, 1'b0);                         // len = channel 0 (R)
        // G channel: lut[i] = 255-i
        for (k = 0; k < 256; k = k + 1) frame_buf[k] = 8'hFF - k[7:0];
        send_frame(8'h03, 8'd1, 1'b0);                         // len = channel 1 (G)
        // B channel: lut[i] = i ^ 0xA5
        for (k = 0; k < 256; k = k + 1) frame_buf[k] = k[7:0] ^ 8'hA5;
        send_frame(8'h03, 8'd2, 1'b0);                         // len = channel 2 (B)
        wait_no_upd(300);
        compare8("S7 R lut[0] unchanged while busy", o_gamma_lut[7:0], 8'h00);
        compare32("S7 o_params_valid still 1", {31'h0, o_params_valid}, 32'h1);
        $display("S7 gamma 3-frame shadow aggregation while busy: done");

        // ---- S8 busy=0: single atomic swap, all 3 channels live ----
        cnt0 = upd_cnt;
        i_rect_busy = 1'b0;
        wait_upd_inc(cnt0, 10);
        compare8("S8 R lut[0]",       o_gamma_lut[8*0         +: 8], 8'h00);
        compare8("S8 R lut[127]",     o_gamma_lut[8*127       +: 8], 8'h7F);
        compare8("S8 R lut[255]",     o_gamma_lut[8*255       +: 8], 8'hFF);
        compare8("S8 G lut[256+0]",   o_gamma_lut[8*256       +: 8], 8'hFF);
        compare8("S8 G lut[256+127]", o_gamma_lut[8*(256+127) +: 8], 8'h80);
        compare8("S8 G lut[256+255]", o_gamma_lut[8*(256+255) +: 8], 8'h00);
        compare8("S8 B lut[512+0]",   o_gamma_lut[8*512       +: 8], 8'hA5);
        compare8("S8 B lut[512+127]", o_gamma_lut[8*(512+127) +: 8], 8'hDA);
        compare8("S8 B lut[512+255]", o_gamma_lut[8*(512+255) +: 8], 8'h5A);
        compare32("S8 o_params_valid", {31'h0, o_params_valid}, 32'h1);
        $display("S8 3-channel LUT atomic swap: done");

        // ---- S9 mode word: gamma_en=1 ----
        frame_buf[0]=8'h01; frame_buf[1]=8'h00; frame_buf[2]=8'h00; frame_buf[3]=8'h00;
        frame_len = 4;
        cnt0 = upd_cnt;                                       // swap fires DURING send (busy=0)
        send_frame(8'h04, 8'd4, 1'b0);
        wait_upd_inc(cnt0, 100);
        compare32("S9 o_gamma_en", {31'h0, o_gamma_en}, 32'h1);
        $display("S9 mode word gamma_en=1: done");

        // ---- S10 bad checksum frame: dropped, params kept ----
        frame_buf[0]=8'h11; frame_buf[1]=8'h22; frame_buf[2]=8'h33; frame_buf[3]=8'h44;
        frame_buf[4]=8'h55; frame_buf[5]=8'h66; frame_buf[6]=8'h77; frame_buf[7]=8'h88;
        frame_len = 32;
        send_frame(8'h01, 8'd32, 1'b1);                        // bad checksum
        wait_no_upd(300);
        compare32("S10 o_fx kept after bad frame", o_fx, 32'h03E8_0000);
        compare32("S10 o_params_valid kept", {31'h0, o_params_valid}, 32'h1);
        $display("S10 bad-checksum frame dropped: done");

        // ---- S11 cmd0x05 status readback: verify 9-byte TX frame ----
        frame_len = 0;                                        // MUST clear: S10 left 32B payload
        send_frame(8'h05, 8'd0, 1'b0);
        for (k = 0; k < 9; k = k + 1) uart_rx_byte(rb[k]);
        compare8("S11 tx[0] hdr AA", rb[0], 8'hAA);
        compare8("S11 tx[1] hdr 55", rb[1], 8'h55);
        compare8("S11 tx[2] cmd 05", rb[2], 8'h05);
        compare8("S11 tx[3] len 04", rb[3], 8'h04);
        compare8("S11 tx[4] st[7:0]",   rb[4], STATUS_VAL[7:0]);
        compare8("S11 tx[5] st[15:8]",  rb[5], STATUS_VAL[15:8]);
        compare8("S11 tx[6] st[23:16]", rb[6], STATUS_VAL[23:16]);
        compare8("S11 tx[7] st[31:24]", rb[7], STATUS_VAL[31:24]);
        compare8("S11 tx[8] checksum",  rb[8],
                 STATUS_VAL[7:0] + STATUS_VAL[15:8] + STATUS_VAL[23:16] + STATUS_VAL[31:24]);
        $display("S11 status readback frame (TX_GAP): done");

        // ---- S12 busy timing recheck: mode frame while busy, then live ----
        i_rect_busy = 1'b1;
        frame_buf[0]=8'h00; frame_buf[1]=8'h00; frame_buf[2]=8'h00; frame_buf[3]=8'h00;
        frame_len = 4;
        send_frame(8'h04, 8'd4, 1'b0);
        wait_no_upd(300);
        compare32("S12 o_gamma_en held while busy", {31'h0, o_gamma_en}, 32'h1);
        cnt0 = upd_cnt;
        i_rect_busy = 1'b0;
        wait_upd_inc(cnt0, 10);
        compare32("S12 o_gamma_en cleared", {31'h0, o_gamma_en}, 32'h0);
        compare32("S12 o_params_valid still 1", {31'h0, o_params_valid}, 32'h1);
        $display("S12 busy timing recheck: done");

        // ---- S13a out-of-range 0x01 (fx = 127.99... < G02 lower bound 128.0) ----
        // Params still go live (the swap itself is NOT blocked); params_valid
        // must drop to 0: param_mgr flags the group, core side refuses to
        // start on it (D06 double insurance, G02 "reject start on violation").
        load_01_payload(32'h007F_FFFF);            // fx = 127.999985, 1 LSB below bound
        frame_len = 32;
        cnt0 = upd_cnt;
        send_frame(8'h01, 8'd32, 1'b0);
        wait_upd_inc(cnt0, 100);
        compare32("S13a o_fx live but out-of-range", o_fx, 32'h007F_FFFF);
        compare32("S13a o_params_valid drops to 0", {31'h0, o_params_valid}, 32'h0);
        $display("S13a out-of-range group flagged invalid: done");

        // ---- S13b boundary-inclusive check (fx = 128.0 exactly) ----
        load_01_payload(32'h0080_0000);             // fx = 128.0, G02 lower bound incl.
        frame_len = 32;
        cnt0 = upd_cnt;
        send_frame(8'h01, 8'd32, 1'b0);
        wait_upd_inc(cnt0, 100);
        compare32("S13b o_fx boundary", o_fx, 32'h0080_0000);
        compare32("S13b o_params_valid boundary inclusive", {31'h0, o_params_valid}, 32'h1);
        $display("S13b G02 lower-bound inclusive: done");

        // ---- S14 restore T3 set ----
        load_01_payload(32'h03E8_0000);             // fx = 1000.0
        frame_len = 32;
        cnt0 = upd_cnt;
        send_frame(8'h01, 8'd32, 1'b0);
        wait_upd_inc(cnt0, 100);
        compare32("S14 o_fx restored", o_fx, 32'h03E8_0000);
        compare32("S14 o_params_valid restored", {31'h0, o_params_valid}, 32'h1);
        $display("S14 T3 param restore: done");

        // ---- Summary ----
        if (upd_cnt !== 10) begin
            $display("FAIL: o_param_updated total pulse count got=%0d exp=10", upd_cnt);
            err = err + 1;
        end
        if (err == 0)
            $display("=== ALL TESTS PASSED (err=0, updated pulses=%0d) ===", upd_cnt);
        else
            $display("=== TEST FAILED: err=%0d ===", err);
        $finish;
    end

endmodule

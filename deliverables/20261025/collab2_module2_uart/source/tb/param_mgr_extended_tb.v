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

module param_mgr_extended_tb;

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
        if (!rst_n) upd_cnt <= 0;
        else if (o_param_updated) upd_cnt <= upd_cnt + 1;
    end
    // 在NBA之后核对全部输出；不允许busy拍更新或无脉冲静默修改。
    wire [6594:0] all_live = {o_fx,o_fy,o_cx,o_cy,o_k1,o_k2,o_p1,o_p2,
        o_a11,o_a12,o_a21,o_a22,o_tx,o_ty,o_aff_en,o_params_valid,o_gamma_en,o_gamma_lut};
    reg [6594:0] previous_live;
    reg busy_at_edge;
    always @(posedge clk) begin
        busy_at_edge = i_rect_busy;
        #1;
        if (rst_n) begin
            if (busy_at_edge && (o_param_updated || all_live !== previous_live)) begin
                $display("FAIL: live group changed while busy"); err=err+1;
            end
            if (all_live !== previous_live && !o_param_updated) begin
                $display("FAIL: live group changed without update flag"); err=err+1;
            end
        end
        previous_live = all_live;
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


    reg signed [31:0] words [0:13];
    reg signed [31:0] low_bound [0:13];
    reg signed [31:0] high_bound [0:13];
    reg [6594:0] held;
    integer n,j,k,before_count,expected_valid;
    task defaults;
        integer t;
        begin
            for(t=0;t<14;t=t+1) words[t]=0;
            words[0]=32'sh03e80000; words[1]=32'sh03e80000;
            words[2]=32'sh03c00000; words[3]=32'sh021c0000;
            words[8]=32'sh00010000; words[11]=32'sh00010000;
        end
    endtask
    task send_words;
        input integer affine;
        integer t,offset;
        begin
            offset=affine ? 8 : 0;
            frame_len=affine ? 25 : 32;
            for(t=0;t<(affine ? 6 : 8);t=t+1) begin
                frame_buf[t*4]=words[t+offset][7:0];
                frame_buf[t*4+1]=words[t+offset][15:8];
                frame_buf[t*4+2]=words[t+offset][23:16];
                frame_buf[t*4+3]=words[t+offset][31:24];
            end
            if(affine) frame_buf[24]=1;
            send_frame(affine ? 8'h02 : 8'h01,affine ? 8'd25 : 8'd32,0);
        end
    endtask
    task swap_and_check;
        input integer legal;
        begin
            @(negedge clk); i_rect_busy=0;
            repeat(5) @(negedge clk);
            if(o_params_valid !== (legal!=0)) begin
                $display("FAIL: boundary index=%0d value=%h valid=%b expected=%0d",n,words[n],o_params_valid,legal);
                err=err+1;
            end
            if ({o_fx,o_fy,o_cx,o_cy,o_k1,o_k2,o_p1,o_p2,o_a11,o_a12,o_a21,o_a22,o_tx,o_ty}
                !== {words[0],words[1],words[2],words[3],words[4],words[5],words[6],words[7],
                     words[8],words[9],words[10],words[11],words[12],words[13]}) begin
                $display("FAIL: entire scalar group mismatch"); err=err+1;
            end
            i_rect_busy=1;
        end
    endtask
    initial begin
        rst_n=0; repeat(10) @(negedge clk); rst_n=1;
        defaults;
        send_words(0); send_words(1);
        swap_and_check(1);
        $display("E0 full group initial load: PASS");
        low_bound[0]=32'sh00800000; high_bound[0]=32'sh7fffffff;
        low_bound[1]=32'sh00800000; high_bound[1]=32'sh7fffffff;
        low_bound[2]=0; high_bound[2]=32'sh077f0000;
        low_bound[3]=0; high_bound[3]=32'sh04370000;
        for(n=4;n<14;n=n+1) begin
            if(n<6) high_bound[n]=32'sh00008000;
            else if(n<8) high_bound[n]=32'sh0000028f;
            else if(n<12) high_bound[n]=32'sh00020000;
            else high_bound[n]=32'sh10000000;
            low_bound[n]=-high_bound[n];
        end
        // 每个字段逐一测两端点及外侧1LSB；fx/fy上端外溢成负数仍应非法。
        for(n=0;n<14;n=n+1) begin
            for(j=0;j<4;j=j+1) begin
                defaults;
                case(j)
                    0: words[n]=low_bound[n];
                    1: words[n]=high_bound[n];
                    2: words[n]=low_bound[n]-1;
                    3: words[n]=high_bound[n]+1;
                endcase
                send_words(0);send_words(1);
                swap_and_check(j<2);
            end
        end
        $display("E1 G02 all 14 fields, endpoints and 1LSB outside (56): done");
        defaults;send_words(0);send_words(1);swap_and_check(1);
        // 连续影子写入覆盖旧值，busy期间保持全部输出包括768字节LUT。
        held=all_live; before_count=upd_cnt;
        words[0]=32'sh04000000;send_words(0);
        words[0]=32'sh05000000;send_words(0);
        for(n=0;n<3;n=n+1) begin
            for(k=0;k<256;k=k+1) frame_buf[k]=(k+n*37)&255;
            frame_len=256;send_frame(8'h03,n,0);
        end
        repeat(10) @(negedge clk);
        if(all_live !== held || upd_cnt!=before_count) begin
            $display("FAIL: busy group was not held");err=err+1;
        end
        n=0;swap_and_check(1);
        if(upd_cnt!=before_count+1) begin $display("FAIL: aggregate swap count");err=err+1;end
        for(n=0;n<3;n=n+1) for(k=0;k<256;k=k+1)
            if(o_gamma_lut[(n*256+k)*8+:8] !== ((k+n*37)&255)) begin
                $display("FAIL: LUT channel=%0d index=%0d",n,k);err=err+1;
            end
        $display("E2 all 768 LUT entries and scalar group atomic hold/swap: done");
        held=all_live;before_count=upd_cnt;
        @(negedge clk);i_rect_busy=0;
        frame_len=4;for(k=0;k<4;k=k+1)frame_buf[k]=0;
        frame_buf[0]=1;send_frame(8'h04,4,1);
        frame_len=0;send_frame(8'h03,3,0); // 非法通道，无负载
        send_frame(8'h02,24,0); // 非法长度，无负载
        repeat(20) @(negedge clk);
        if(all_live !== held || upd_cnt!=before_count) begin
            $display("FAIL: rejected frame altered live group");err=err+1;
        end
        $display("E3 checksum/length/channel rejection: done");
        // 新分发与旧dirty切换同拍：旧组先切、新组下一拍切，不丢新命令。
        i_rect_busy=1;words[0]=32'sh06000000;send_words(0);
        words[0]=32'sh07000000;
        fork
            send_words(0);
            begin
                @(posedge dut.disp_valid);@(negedge clk);i_rect_busy=0;
                @(negedge clk);
                compare32("E4 old shadow",o_fx,32'h06000000);
                compare32("E4 update old",{31'd0,o_param_updated},1);
                @(negedge clk);
                compare32("E4 new shadow",o_fx,32'h07000000);
                compare32("E4 update new",{31'd0,o_param_updated},1);
            end
        join
        repeat(8) @(negedge clk);
        if(dut.sh_dirty!==0) begin $display("FAIL: dirty not cleared");err=err+1;end
        $display("E4 coincident dispatch/swap: two adjacent update cycles, latest value retained");
        if(err==0) $display("=== ALL TESTS PASSED (err=0) ===");
        else $display("=== TEST FAILED: err=%0d ===",err);
        $finish;
    end
endmodule

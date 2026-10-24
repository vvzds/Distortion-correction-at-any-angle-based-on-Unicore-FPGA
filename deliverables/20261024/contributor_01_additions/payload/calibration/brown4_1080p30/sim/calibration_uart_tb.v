`timescale 1ns/1ps
module calibration_uart_tb;
    `include "parameters/calibration_q16.vh"
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,rx=1,busy=0;
    wire updated,valid,aff_en,gamma_en;
    wire signed [31:0] fx,fy,cx,cy,k1,k2,p1,p2;
    reg [7:0] frame_data[0:36];
    integer n,b,updates=0;
    param_mgr #(.CLK_FREQ(125000000),.BAUD_RATE(115200)) dut(
        .clk(clk),.rst_n(rst_n),.i_uart_rx(rx),.o_uart_tx(),.i_rect_busy(busy),
        .o_param_updated(updated),.o_params_valid(valid),.o_fx(fx),.o_fy(fy),
        .o_cx(cx),.o_cy(cy),.o_k1(k1),.o_k2(k2),.o_p1(p1),.o_p2(p2),
        .o_aff_a11(),.o_aff_a12(),.o_aff_a21(),.o_aff_a22(),.o_aff_tx(),.o_aff_ty(),
        .o_aff_en(aff_en),.o_gamma_en(gamma_en),.o_gamma_lut(),
        .o_hist_rd_en(),.o_hist_ch(),.i_hist_count(24'd0),.i_status(32'd0));
    always @(posedge clk)if(updated)updates=updates+1;
    task send_byte;
        input [7:0] value;
        integer bit_index;
        begin
            @(negedge clk);rx=0;repeat(1085)@(negedge clk);
            for(bit_index=0;bit_index<8;bit_index=bit_index+1) begin
                rx=value[bit_index];repeat(1085)@(negedge clk);
            end
            rx=1;repeat(1085)@(negedge clk);
        end
    endtask
    task check_group;
        input integer real_group;
        begin
            if(fx!==CAL_FX||fy!==CAL_FY||cx!==CAL_CX||cy!==CAL_CY||
                k1!==(real_group?CAL_K1:32'sd0)||k2!==(real_group?CAL_K2:32'sd0)||
                p1!==(real_group?CAL_P1:32'sd0)||p2!==(real_group?CAL_P2:32'sd0)||
                valid!==1||aff_en!==0||gamma_en!==0) $fatal(1,"UART decoded group mismatch");
        end
    endtask
    initial begin
        #30;rst_n=1;
        $readmemh("vectors/identity_uart_bytes.hex",frame_data);
        for(n=0;n<37;n=n+1)send_byte(frame_data[n]);
        repeat(3000)@(negedge clk);check_group(0);
        if(updates!=1)$fatal(1,"UART identity update count");
        busy=1;
        $readmemh("vectors/real_uart_bytes.hex",frame_data);
        for(n=0;n<37;n=n+1)send_byte(frame_data[n]);
        repeat(3000)@(negedge clk);check_group(0);
        if(updates!=1)$fatal(1,"UART changed live parameters while busy");
        busy=0;repeat(12)@(negedge clk);check_group(1);
        if(updates!=2)$fatal(1,"UART real update count");
        $display("UART PASS actual_115200_8N1=1 identity_and_real_decode=1 busy_atomic=1 updates=%0d",updates);
        $finish;
    end
    initial begin #10000000;$fatal(1,"UART TIMEOUT");end
endmodule

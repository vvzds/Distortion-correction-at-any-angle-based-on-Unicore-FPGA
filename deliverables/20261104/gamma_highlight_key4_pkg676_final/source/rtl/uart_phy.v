`timescale 1ns/1ps
// 8-N-1 UART transmitter/receiver with a two-flop RX synchronizer.
// rx_valid/rx_error are one-clock pulses; DIV is integer clocks per bit.
// The caller holds tx_data stable while tx_valid is asserted and tx_busy is low.
module uart_phy #(parameter CLOCK_HZ=125000000,parameter BAUD=115200)(
    input wire clk,rst_n,rx,
    output reg tx,
    output reg rx_valid,rx_error,
    output reg [7:0] rx_data,
    input wire tx_valid,
    input wire [7:0] tx_data,
    output wire tx_busy
);
    localparam DIV=CLOCK_HZ/BAUD;
    (* syn_preserve=1 *) reg [1:0] rx_sync;
    reg [1:0] rs;
    reg [15:0] rc,tc;
    reg [2:0] rb;
    reg [7:0] shift;
    reg [9:0] tx_shift;
    reg [3:0] remaining;
    reg tx_active;
    assign tx_busy=tx_active;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) rx_sync<=2'b11;
        else rx_sync<={rx_sync[0],rx};
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin rs<=0;rc<=0;rb<=0;shift<=0;rx_valid<=0;rx_error<=0;rx_data<=0;end
        else begin
            rx_valid<=0;rx_error<=0;
            case(rs)
                0: if(!rx_sync[1]) begin rc<=DIV/2-1;rs<=1;end
                1: if(rc!=0) rc<=rc-1'b1;
                   else if(!rx_sync[1]) begin rc<=DIV-1;rb<=0;rs<=2;end
                   else rs<=0;
                2: if(rc!=0) rc<=rc-1'b1;
                   else begin
                       shift[rb]<=rx_sync[1];rc<=DIV-1;
                       if(rb==7) rs<=3;else rb<=rb+1'b1;
                   end
                3: if(rc!=0) rc<=rc-1'b1;
                   else begin
                       rs<=0;
                       if(rx_sync[1]) begin rx_valid<=1;rx_data<=shift;end
                       else rx_error<=1;
                   end
            endcase
        end
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin tx<=1;remaining<=0;tc<=0;tx_shift<=10'h3ff;tx_active<=0;end
        else if(!tx_active) begin
            tx<=1;
            if(tx_valid) begin tx_shift<={1'b1,tx_data,1'b0};tx<=0;remaining<=10;tc<=DIV-1;tx_active<=1;end
        end else if(tc!=0) tc<=tc-1'b1;
        else begin
            remaining<=remaining-1'b1;tx_shift<={1'b1,tx_shift[9:1]};
            tx<=tx_shift[1];tc<=DIV-1;
            if(remaining==1) tx_active<=0;
        end
    end
endmodule

`timescale 1ns/1ps
// SPI mode 3, MSB first. 125MHz/128 = 0.977MHz; ample margin to 3MHz limit.
// CS belongs to transaction layer; wait at least HALF_DIV before first edge.
module bno_spi_byte #(parameter HALF_DIV=64)(
    input wire clk,rst_n,start,
    input wire [7:0] tx_data,
    input wire miso,
    output reg sck,mosi,busy,done,
    output reg [7:0] rx_data
);
    reg [15:0] count;
    reg [7:0] tx_shift,rx_shift;
    reg [2:0] bit_index;
    // MISO is stable for ~500ns before sampling; two-stage synchronization
    // adds 16ns and avoids propagating asynchronous pin transitions.
    (* syn_preserve=1 *) reg [1:0] miso_sync;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) miso_sync<=0;else miso_sync<={miso_sync[0],miso};
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            sck<=1;mosi<=0;busy<=0;done<=0;rx_data<=0;
            count<=0;tx_shift<=0;rx_shift<=0;bit_index<=0;
        end else begin
            done<=0;
            if(!busy) begin
                sck<=1;
                if(start) begin
                    busy<=1;count<=HALF_DIV-1;tx_shift<=tx_data;
                    bit_index<=7;rx_shift<=0;
                end
            end else if(count!=0) count<=count-1'b1;
            else begin
                count<=HALF_DIV-1;
                if(sck) begin sck<=0;mosi<=tx_shift[7];end
                else begin
                    sck<=1;rx_shift<={rx_shift[6:0],miso_sync[1]};
                    tx_shift<={tx_shift[6:0],1'b0};
                    if(bit_index==0) begin
                        busy<=0;done<=1;rx_data<={rx_shift[6:0],miso_sync[1]};
                    end else bit_index<=bit_index-1'b1;
                end
            end
        end
    end
endmodule

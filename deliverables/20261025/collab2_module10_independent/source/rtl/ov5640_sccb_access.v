`timescale 1ns/1ps
// 单主机SCCB读写候选；开漏输出1表示拉低，0表示释放。
// 支持16位寄存器地址、1字节数据、重复起始读、NACK及超时。
module ov5640_sccb_access #(
    parameter HALF_CYCLES=675,
    parameter TIMEOUT_CYCLES=270000,
    parameter [6:0] DEVICE_ADDR=7'h3c
)(
    input wire clk,input wire rst_n,
    input wire req_valid,output wire req_ready,
    input wire req_read,input wire [15:0] req_addr,input wire [7:0] req_wdata,
    output reg rsp_valid,output reg rsp_error,output reg [7:0] rsp_rdata,
    input wire scl_in,input wire sda_in,
    output reg scl_low,output reg sda_low
);
    localparam IDLE=0,START0=1,START1=2,TX0=3,TX1=4,TX2=5,
      ACK0=6,ACK1=7,ACK2=8,RS0=9,RS1=10,RS2=11,
      RX0=12,RX1=13,RX2=14,NA0=15,NA1=16,NA2=17,
      STOP0=18,STOP1=19,STOP2=20,TX_RISE=21,ACK_RISE=22,
      RS_RISE=23,RX_RISE=24,NA_RISE=25,STOP_RISE=26;
    reg [4:0] state;
    reg [31:0] divider,watchdog;
    reg [1:0] scl_sync,sda_sync;
    reg [7:0] tx_byte,rx_byte,data_latch;
    reg [15:0] addr_latch;
    reg read_latch;
    reg [2:0] bit_index,byte_index;
    wire high_phase=(state==START0 || state==START1 || state==TX1 ||
      state==ACK1 || state==RS1 || state==RS2 || state==RX1 ||
      state==NA1 || state==STOP1 || state==STOP2);
    assign req_ready=(state==IDLE);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin scl_sync<=3;sda_sync<=3;end
        else begin scl_sync<={scl_sync[0],scl_in};sda_sync<={sda_sync[0],sda_in};end
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;divider<=0;watchdog<=0;
            scl_low<=0;sda_low<=0;rsp_valid<=0;rsp_error<=0;rsp_rdata<=0;
            tx_byte<=0;rx_byte<=0;addr_latch<=0;data_latch<=0;
            read_latch<=0;bit_index<=7;byte_index<=0;
        end else begin
            rsp_valid<=0;
            if(state==IDLE) begin
                scl_low<=0;sda_low<=0;divider<=0;watchdog<=0;
                if(req_valid) begin
                    read_latch<=req_read;addr_latch<=req_addr;data_latch<=req_wdata;
                    tx_byte<={DEVICE_ADDR,1'b0};bit_index<=7;byte_index<=0;
                    rx_byte<=0;rsp_error<=0;state<=START0;
                end
            end else if(watchdog==TIMEOUT_CYCLES-1) begin
                state<=IDLE;scl_low<=0;sda_low<=0;rsp_valid<=1;rsp_error<=1;
            end else begin
                watchdog<=watchdog+1'b1;
                if(high_phase && !scl_sync[1]) divider<=0;
                else if(divider==HALF_CYCLES-1) begin
                    divider<=0;
                    case(state)
                     START0:if(sda_sync[1]) begin sda_low<=1;state<=START1;end
                     START1:begin scl_low<=1;state<=TX0;end
                     TX0:begin sda_low<=~tx_byte[bit_index];state<=TX_RISE;end
                     TX_RISE:begin scl_low<=0;state<=TX1;end
                     TX1:begin scl_low<=1;state<=TX2;end
                     TX2:if(bit_index==0) state<=ACK0;
                         else begin bit_index<=bit_index-1'b1;state<=TX0;end
                     ACK0:begin sda_low<=0;state<=ACK_RISE;end
                     ACK_RISE:begin scl_low<=0;state<=ACK1;end
                     ACK1:begin
                        scl_low<=1;
                        if(sda_sync[1]) begin rsp_error<=1;state<=STOP0;end
                        else state<=ACK2;
                     end
                     ACK2:begin
                        bit_index<=7;byte_index<=byte_index+1'b1;state<=TX0;
                        case(byte_index)
                         0:tx_byte<=addr_latch[15:8];
                         1:tx_byte<=addr_latch[7:0];
                         2:if(read_latch) state<=RS0;else tx_byte<=data_latch;
                         3:if(read_latch) state<=RX0;else state<=STOP0;
                         default:begin rsp_error<=1;state<=STOP0;end
                        endcase
                     end
                     RS0:begin sda_low<=0;state<=RS_RISE;end
                     RS_RISE:begin scl_low<=0;state<=RS1;end
                     RS1:begin sda_low<=1;state<=RS2;end
                     RS2:begin scl_low<=1;tx_byte<={DEVICE_ADDR,1'b1};state<=TX0;end
                     RX0:begin sda_low<=0;state<=RX_RISE;end
                     RX_RISE:begin scl_low<=0;state<=RX1;end
                     RX1:begin rx_byte[bit_index]<=sda_sync[1];scl_low<=1;state<=RX2;end
                     RX2:if(bit_index==0) state<=NA0;
                         else begin bit_index<=bit_index-1'b1;state<=RX0;end
                     NA0:begin sda_low<=0;state<=NA_RISE;end
                     NA_RISE:begin scl_low<=0;state<=NA1;end
                     NA1:begin scl_low<=1;state<=NA2;end
                     NA2:begin rsp_rdata<=rx_byte;state<=STOP0;end
                     STOP0:begin scl_low<=1;sda_low<=1;state<=STOP_RISE;end
                     STOP_RISE:begin scl_low<=0;state<=STOP1;end
                     STOP1:state<=STOP2;
                     STOP2:begin sda_low<=0;state<=IDLE;rsp_valid<=1;end
                     default:begin state<=IDLE;rsp_valid<=1;rsp_error<=1;end
                    endcase
                end else divider<=divider+1'b1;
            end
        end
    end
endmodule

`timescale 1ns/1ps
// Independent protocol v1: AA 55 version command length seqLE payload CRC16LE.
// CRC16/CCITT-FALSE covers version through final payload byte. SET(10h) carries
// all 16 registers atomically. STATUS(20h) returns A0h/48 bytes. No legacy UART
// packet is accepted. Received data never alters an in-flight frame.
// Quality commands 30h/32h set sharpen/denoise levels at the next video frame;
// 34h writes an OSD row and 35h changes visibility. Row data crosses to the pixel
// domain only through the held-payload toggle handshake in video_osd.
module host_control #(parameter CLOCK_HZ=125000000,parameter BAUD=115200)(
    input wire clk,rst_n,uart_rx,
    output wire uart_tx,
    input wire busy,
    input wire [383:0] imu_snapshot,imu_diagnostics,
    output reg imu_restart,imu_map_update,
    output reg [2:0] imu_baud_code,
    output reg imu_map_enable,imu_capture_toggle,
    output reg [1:0] denoise_level,sharpen_level,
    output reg quality_update,osd_update,
    output reg osd_row_valid,osd_visible,
    output reg [2:0] osd_row_index,
    output reg [383:0] osd_row_data,
    input wire [255:0] telemetry,
    input wire [511:0] published_cfg,
    output reg [511:0] cfg,
    output reg pending,
    output reg [15:0] active_sequence,
    output reg [31:0] rx_errors,valid_packets
);
    `include "source/rtl/default_config.vh"
    wire rx_valid,rx_error,tx_busy;wire [7:0] rx_data;
    wire tx_valid;reg [7:0] tx_data;
    uart_phy #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) u_phy(
        .clk(clk),.rst_n(rst_n),.rx(uart_rx),.tx(uart_tx),
        .rx_valid(rx_valid),.rx_error(rx_error),.rx_data(rx_data),
        .tx_valid(tx_valid),.tx_data(tx_data),.tx_busy(tx_busy));
    function [15:0] crc_byte;
        input [15:0] old_crc;input [7:0] b;
        reg [15:0] c;integer k;
        begin
            c=old_crc^{b,8'd0};
            for(k=0;k<8;k=k+1) c=c[15]?(c<<1)^16'h1021:c<<1;
            crc_byte=c;
        end
    endfunction
    reg [3:0] state;
    reg [7:0] command,length,byte_index,crc_low;
    reg [15:0] sequence_rx,pending_sequence,rx_crc;
    reg [511:0] packet_data,shadow;
    reg [21:0] timeout_count;
    wire [31:0] sfx=packet_data[6*32+:32],sfy=packet_data[7*32+:32];
    wire [31:0] scx=packet_data[8*32+:32],scy=packet_data[9*32+:32];
    wire projective_packet=packet_data[14*32+3];
    wire parameters_ok=sfx>=32'd8388608 && sfx<=32'd536805376 &&
                       sfy>=32'd8388608 && sfy<=32'd536805376 &&
                       scx<=32'd125763584 && scy<=32'd70713344 &&
                       packet_data[10*32+24+:8]=={8{packet_data[10*32+23]}} &&
                       packet_data[11*32+24+:8]=={8{packet_data[11*32+23]}} &&
                       packet_data[12*32+24+:8]=={8{packet_data[12*32+23]}} &&
                       packet_data[13*32+24+:8]=={8{packet_data[13*32+23]}} &&
                       (projective_packet ? packet_data[14*32+4+:12]==0 :
                        (packet_data[14*32+:32]<=1 && packet_data[15*32+18+:14]==0));
    reg tx_active;
    reg [5:0] tx_index;
    reg [15:0] tx_sequence,tx_crc;
    reg [383:0] snapshot;
    reg [7:0] response_command;
    assign tx_valid=tx_active && !tx_busy;
    always @* begin
        case(tx_index)
            0:tx_data=8'haa;1:tx_data=8'h55;2:tx_data=1;3:tx_data=response_command;4:tx_data=48;
            5:tx_data=tx_sequence[7:0];6:tx_data=tx_sequence[15:8];
            55:tx_data=tx_crc[7:0];56:tx_data=tx_crc[15:8];
            default:tx_data=snapshot[(tx_index-7)*8+:8];
        endcase
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            cfg<={DEFAULT_15,DEFAULT_14,DEFAULT_13,DEFAULT_12,DEFAULT_11,DEFAULT_10,
                  DEFAULT_9,DEFAULT_8,DEFAULT_7,DEFAULT_6,DEFAULT_5,DEFAULT_4,
                  DEFAULT_3,DEFAULT_2,DEFAULT_1,DEFAULT_0};
            shadow<=0;pending<=0;active_sequence<=0;pending_sequence<=0;
            state<=0;command<=0;length<=0;byte_index<=0;crc_low<=0;
            sequence_rx<=0;rx_crc<=16'hffff;packet_data<=0;timeout_count<=0;
            rx_errors<=0;valid_packets<=0;imu_map_enable<=0;imu_map_update<=0;imu_capture_toggle<=0;tx_active<=0;tx_index<=0;
            tx_sequence<=0;tx_crc<=16'hffff;snapshot<=0;response_command<=8'ha0;imu_baud_code<=0;imu_restart<=0;
            denoise_level<=0;sharpen_level<=0;osd_row_valid<=0;osd_visible<=0;
            quality_update<=0;osd_update<=0;
            osd_row_index<=0;osd_row_data<=0;
        end else begin
            osd_row_valid<=0;
            quality_update<=0;osd_update<=0;
            imu_map_update<=0;
            if(pending && !busy) begin cfg<=shadow;active_sequence<=pending_sequence;pending<=0;end
            if(tx_valid) begin
                tx_index<=tx_index+1'b1;
                if(tx_index>=2 && tx_index<=54) tx_crc<=crc_byte(tx_crc,tx_data);
                if(tx_index==56) tx_active<=0;
            end
            if(rx_error) begin rx_errors<=rx_errors+1'b1;state<=0;end
            if(state!=0) begin
                if(timeout_count==CLOCK_HZ/50) begin state<=0;timeout_count<=0;rx_errors<=rx_errors+1'b1;end
                else timeout_count<=timeout_count+1'b1;
            end else timeout_count<=0;
            if(rx_valid) begin
                timeout_count<=0;
                if(state>=2 && state<=7) rx_crc<=crc_byte(rx_crc,rx_data);
                case(state)
                    0:if(rx_data==8'haa) state<=1;
                    1:if(rx_data==8'h55) begin state<=2;rx_crc<=16'hffff;end
                      else if(rx_data!=8'haa) state<=0;
                    2:if(rx_data==1) state<=3;else begin state<=0;rx_errors<=rx_errors+1'b1;end
                    3:begin command<=rx_data;state<=4;end
                    4:begin
                        length<=rx_data;
                        if((command==8'h10 && rx_data==64) ||
                           ((command==8'h20 || command==8'h21 || command==8'h22 || command==8'h24 || command==8'h25) && rx_data==0) ||
                           ((command==8'h23 || command==8'h26 || command==8'h30 || command==8'h32 || command==8'h35) && rx_data==1) ||
                           (command==8'h34 && rx_data==49)) state<=5;
                        else begin state<=0;rx_errors<=rx_errors+1'b1;end
                    end
                    5:begin sequence_rx[7:0]<=rx_data;state<=6;end
                    6:begin sequence_rx[15:8]<=rx_data;byte_index<=0;state<=length==0?8:7;end
                    7:begin
                        packet_data[byte_index*8+:8]<=rx_data;byte_index<=byte_index+1'b1;
                        if(byte_index==length-1'b1) state<=8;
                    end
                    8:begin crc_low<=rx_data;state<=9;end
                    9:begin
                        state<=0;
                        if({rx_data,crc_low}!=rx_crc) rx_errors<=rx_errors+1'b1;
                        else if(command==8'h10) begin
                            if(parameters_ok) begin
                                shadow<=packet_data;pending_sequence<=sequence_rx;pending<=1;
                                valid_packets<=valid_packets+1'b1;
                            end else rx_errors<=rx_errors+1'b1;
                        end else if(command==8'h23) begin
                            if(packet_data[7:0]<=2) begin imu_baud_code<=packet_data[2:0];valid_packets<=valid_packets+1'b1;end
                            else rx_errors<=rx_errors+1'b1;
                        end else if(command==8'h24) begin
                            imu_restart<=~imu_restart;valid_packets<=valid_packets+1'b1;
                        end else if(command==8'h26) begin
                            if(packet_data[7:0]==0) begin
                                imu_map_enable<=0;imu_map_update<=1;valid_packets<=valid_packets+1'b1;
                            end else if(packet_data[7:0]==1) begin
                                imu_map_enable<=1;imu_map_update<=1;imu_capture_toggle<=~imu_capture_toggle;
                                valid_packets<=valid_packets+1'b1;
                            end else rx_errors<=rx_errors+1'b1;
                        end else if(command==8'h30) begin
                            if(packet_data[7:0]<=3) begin sharpen_level<=packet_data[1:0];quality_update<=1;valid_packets<=valid_packets+1'b1;end
                            else rx_errors<=rx_errors+1'b1;
                        end else if(command==8'h32) begin
                            if(packet_data[7:0]<=3) begin denoise_level<=packet_data[1:0];quality_update<=1;valid_packets<=valid_packets+1'b1;end
                            else rx_errors<=rx_errors+1'b1;
                        end else if(command==8'h34) begin
                            if(packet_data[7:0]<8) begin
                                osd_row_index<=packet_data[2:0];
                                osd_row_data<=packet_data[8+:384];
                                osd_row_valid<=1;
                                valid_packets<=valid_packets+1'b1;
                            end else rx_errors<=rx_errors+1'b1;
                        end else if(command==8'h35) begin
                            if(packet_data[7:0]<=1) begin osd_visible<=packet_data[0];osd_update<=1;valid_packets<=valid_packets+1'b1;end
                            else rx_errors<=rx_errors+1'b1;
                        end else if((command==8'h20 || command==8'h21 || command==8'h22 || command==8'h25) && !tx_active && !tx_busy) begin
                            valid_packets<=valid_packets+1'b1;
                            snapshot<={valid_packets,rx_errors,telemetry,
                                       pending_sequence,active_sequence,32'h554e4401};
                            if(command==8'h21)
                                snapshot<={32'h00020001,published_cfg[15*32+:32],
                                           published_cfg[14*32+:32],telemetry[31:0],
                                           published_cfg[0+:192],telemetry[31:0],32'h534d5432};
                            if(command==8'h22) snapshot<=imu_snapshot;
                            if(command==8'h25) snapshot<=imu_diagnostics;
                            response_command<=command|8'h80;
                            tx_sequence<=sequence_rx;tx_crc<=16'hffff;tx_index<=0;tx_active<=1;
                        end
                    end
                    default:state<=0;
                endcase
            end
        end
    end
endmodule

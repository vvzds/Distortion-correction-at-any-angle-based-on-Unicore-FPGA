`include "source/rtl/video_contract.vh"
`timescale 1ns/1ps
// Random tile-row packets, exactly 64 pixels (4 native beats). Two packets
// decouple rendering from DDR command/data pulls. A frame publishes only after
// every word is accepted, COMMIT arrives, and the final native LAST is drained.
// Frame-slot range and contiguous address within each tile row are checked.
module tile_write_pack #(
    parameter FRAME_WORDS=`VC_FRAME_WORDS,
    parameter SLOT_BITS=`VC_SLOT_WORD_BITS
)(
    input wire clk,rst_n,begin_frame,
    input wire [2:0] frame_slot,
    input wire corr_wr_req,
    input wire [23:0] corr_wr_addr,
    input wire [31:0] corr_wr_data,
    output wire corr_wr_gnt,
    input wire corr_wr_commit,
    output wire frame_idle,
    output reg publish,protocol_error,
    output wire [23:0] awaddr,
    output wire [3:0] awlen,
    output wire awvalid,
    input wire awready,
    output wire [255:0] wdata,
    input wire wpull,wlast
);
    reg [255:0] data[0:7];
    reg [23:0] address[0:1];
    reg [1:0] full;
    reg wr_bank,rd_bank,active,sent,committed;
    reg [4:0] fill;
    reg [1:0] beat;
    reg [20:0] accepted;
    reg [2:0] slot;
    reg [23:0] expected;
    wire address_ok=corr_wr_addr[23:20]=={1'b0,slot} &&
                    corr_wr_addr[19:0]<FRAME_WORDS &&
                    ((fill==0 && corr_wr_addr[4:0]==0) ||
                     (fill!=0 && corr_wr_addr==expected));
    assign corr_wr_gnt=rst_n && active && !committed && !protocol_error &&
                       !full[wr_bank] && accepted<FRAME_WORDS && address_ok;
    assign frame_idle=!active;
    assign awaddr=address[rd_bank];assign awlen=4'd3;
    assign awvalid=rst_n && full[rd_bank] && !sent;
    assign wdata=data[{rd_bank,beat}];
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            full<=0;wr_bank<=0;rd_bank<=0;active<=0;sent<=0;committed<=0;
            fill<=0;beat<=0;accepted<=0;slot<=0;expected<=0;publish<=0;protocol_error<=0;
        end else begin
            publish<=0;
            if(begin_frame && !active) begin
                active<=1;committed<=0;accepted<=0;slot<=frame_slot;
                full<=0;fill<=0;wr_bank<=0;rd_bank<=0;sent<=0;beat<=0;
            end
            if(corr_wr_req && corr_wr_gnt) begin
                data[{wr_bank,fill[4:3]}][fill[2:0]*32+:32]<=corr_wr_data;
                if(fill==0) address[wr_bank]<=corr_wr_addr;
                expected<=corr_wr_addr+1'b1;
                accepted<=accepted+1'b1;fill<=fill+1'b1;
                if(fill==31) begin full[wr_bank]<=1;wr_bank<=!wr_bank;end
            end
            if(awvalid && awready) begin sent<=1;beat<=0;end
            if(sent && wpull) beat<=beat+1'b1;
            if(sent && wpull && wlast) begin full[rd_bank]<=0;rd_bank<=!rd_bank;sent<=0;beat<=0;end
            if(active && corr_wr_commit) begin
                committed<=1;
                if(accepted!=FRAME_WORDS || fill!=0) protocol_error<=1;
            end
            if(active && committed && full==0 && !sent && accepted==FRAME_WORDS) begin
                publish<=1;active<=0;committed<=0;
            end
        end
    end
endmodule

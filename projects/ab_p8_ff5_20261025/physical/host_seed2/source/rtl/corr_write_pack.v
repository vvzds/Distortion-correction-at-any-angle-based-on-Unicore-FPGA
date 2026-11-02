`include "source/rtl/video_contract.vh"
`timescale 1ns/1ps
// One corrected frame at a time, contiguous full 32-bit words. Eight native
// beats are assembled BEFORE AW: the Pango IP pulls data without WVALID.
// Backpressure between packets prevents overflow. Publication waits for LAST.
module corr_write_pack #(
    parameter FRAME_WORDS=`VC_FRAME_WORDS,
    parameter SLOT_BITS=`VC_SLOT_WORD_BITS
)(
    input wire clk, rst_n,
    input wire begin_frame,
    input wire [2:0] frame_slot,
    input wire corr_wr_req,
    input wire [23:0] corr_wr_addr,
    input wire [31:0] corr_wr_data,
    output wire corr_wr_gnt,
    input wire corr_wr_commit,
    output wire frame_idle,
    output reg publish,
    output reg protocol_error,
    output wire [23:0] awaddr,
    output wire [3:0] awlen,
    output wire awvalid,
    input wire awready,
    output wire [255:0] wdata,
    input wire wpull, wlast
);
    localparam PACKET_WORDS=`VC_WRITE_BURST_BEATS*8;
    reg [255:0] buffer [0:`VC_WRITE_BURST_BEATS-1];
    reg active, committed, packet_ready, packet_sent;
    reg [5:0] fill;
    reg [2:0] beat;
    reg [23:0] expected_addr, packet_addr;
    reg [20:0] accepted_words;
    assign frame_idle = !active;
    assign corr_wr_gnt = rst_n && active && !committed && !packet_ready &&
                         accepted_words < FRAME_WORDS && corr_wr_addr == expected_addr;
    assign awaddr=packet_addr;
    assign awlen=`VC_WRITE_BURST_BEATS-1;
    assign awvalid=packet_ready && !packet_sent;
    assign wdata=buffer[beat];
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active<=0; committed<=0; packet_ready<=0; packet_sent<=0;
            fill<=0; beat<=0; expected_addr<=0; packet_addr<=0;
            accepted_words<=0; publish<=0; protocol_error<=0;
        end else begin
            publish<=0;
            if (begin_frame && !active) begin
                active<=1; committed<=0; fill<=0; beat<=0;
                accepted_words<=0;
                expected_addr<=frame_slot<<SLOT_BITS;
                packet_addr<=frame_slot<<SLOT_BITS;
            end
            if (corr_wr_req && corr_wr_gnt) begin
                buffer[fill[5:3]][fill[2:0]*32 +: 32]<=corr_wr_data;
                fill<=fill+1'b1;
                expected_addr<=expected_addr+1'b1;
                accepted_words<=accepted_words+1'b1;
                if (fill == PACKET_WORDS-1) begin
                    packet_ready<=1; beat<=0;
                end
            end
            if (awvalid && awready) packet_sent<=1;
            if (packet_sent && wpull) beat<=beat+1'b1;
            if (packet_sent && wlast) begin
                packet_sent<=0; packet_ready<=0; beat<=0;
                packet_addr<=expected_addr;
            end
            if (active && corr_wr_commit) begin
                committed<=1;
                if (accepted_words + (corr_wr_req && corr_wr_gnt) != FRAME_WORDS)
                    protocol_error<=1;
            end
            if (active && committed && !packet_ready && fill == 0 &&
                accepted_words == FRAME_WORDS) begin
                publish<=1; active<=0; committed<=0;
            end
        end
    end
endmodule

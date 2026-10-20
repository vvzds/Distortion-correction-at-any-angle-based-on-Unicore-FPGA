`include "source/rtl/video_contract.vh"
`timescale 1ns/1ps
// A single allocated target remains reserved through COMMIT and drain.
// Accepted safety variation: next allocation waits until previous publication.
module corr_slot_ctrl (
    input wire clk,rst_n,
    input wire rd_start,
    input wire corr_wr_slot_req,
    input wire writer_idle,publish,
    output wire corr_wr_slot_gnt,
    output wire [2:0] corr_wr_slot,
    output reg [1:0] rd_bank,
    output reg display_valid
);
    reg active,latest_valid;
    reg [1:0] wr_bank,latest_bank,next_bank;
    reg found;
    reg [1:0] candidate;
    integer i;
    always @* begin
        next_bank=wr_bank; found=0; candidate=wr_bank;
        for (i=1;i<4;i=i+1) begin
            candidate=wr_bank+i;
            if (!found && (!display_valid || candidate!=rd_bank) &&
                (!latest_valid || candidate!=latest_bank)) begin
                next_bank=candidate; found=1;
            end
        end
    end
    assign corr_wr_slot_gnt=rst_n && corr_wr_slot_req && !active && writer_idle && found;
    // The combinational candidate is valid on the grant edge, then latched.
    assign corr_wr_slot={1'b1,active ? wr_bank : next_bank};
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active<=0; latest_valid<=0; wr_bank<=0; latest_bank<=0;
            rd_bank<=0; display_valid<=0;
        end else begin
            if (corr_wr_slot_gnt) begin active<=1; wr_bank<=next_bank; end
            if (active && publish) begin
                active<=0; latest_valid<=1; latest_bank<=wr_bank;
            end
            if (rd_start && latest_valid) begin
                rd_bank<=latest_bank; display_valid<=1;
            end
        end
    end
endmodule

`timescale 1ns / 1ps
// All ownership decisions run in the DDR core clock domain. Four frame slots
// keep the displayed frame and newest completed frame out of the writer's way.
module frame_bank_ctrl #(parameter CORR_ENABLE = 0) (
    input wire clk,
    input wire rst_n,
    input wire wr_start,
    input wire wr_complete,
    input wire rd_start,
    output reg [1:0] wr_bank,
    output reg [1:0] rd_bank,
    output reg [1:0] o_frame_wcnt,
    output reg o_frame_update,
    input wire corr_src_hold_req,
    output reg corr_src_hold_gnt,
    output reg [1:0] corr_src_slot,
    input wire corr_src_rel,
    output reg display_valid
);
    reg [1:0] latest_bank;
    reg latest_valid;
    reg [1:0] next_bank;
    reg found;
    integer i;
    reg [1:0] candidate;

    // A grant concurrent with completion locks the newly completed bank.
    wire new_hold = CORR_ENABLE && corr_src_hold_req &&
                    !corr_src_hold_gnt && !corr_src_rel && (wr_complete || latest_valid);
    wire [1:0] hold_target = wr_complete ? wr_bank : latest_bank;
    wire [1:0] effective_latest = (CORR_ENABLE && wr_complete) ? wr_bank : latest_bank;
    always @* begin
        next_bank = wr_bank;
        found = 1'b0;
        candidate = wr_bank;
        for (i = 1; i < 4; i = i + 1) begin
            candidate = wr_bank + i;
            if (!found &&
                (!display_valid || candidate != rd_bank) &&
                (!latest_valid || candidate != effective_latest) &&
                (!CORR_ENABLE || !corr_src_hold_gnt || candidate != corr_src_slot) &&
                (!new_hold || candidate != hold_target)) begin
                next_bank = candidate;
                found = 1'b1;
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            o_frame_wcnt <= 2'd0;
            o_frame_update <= 1'b0;
            corr_src_hold_gnt <= 1'b0;
            corr_src_slot <= 2'd0;
            wr_bank <= 2'd0;
            rd_bank <= 2'd0;
            latest_bank <= 2'd0;
            latest_valid <= 1'b0;
            display_valid <= 1'b0;
        end else begin
            o_frame_update <= wr_complete;
            if (wr_complete) o_frame_wcnt <= wr_bank;
            if (!CORR_ENABLE || corr_src_rel) corr_src_hold_gnt <= 1'b0;
            else if (new_hold) begin
                corr_src_hold_gnt <= 1'b1;
                corr_src_slot <= hold_target;
            end
            if (wr_start)
                wr_bank <= next_bank;
            if (wr_complete) begin
                latest_bank <= wr_bank;
                latest_valid <= 1'b1;
            end
            // Latch only at the start of HDMI vertical blanking. Reuse a full
            // frame when the camera is late; intermediate full frames may drop.
            if (rd_start && latest_valid) begin
                rd_bank <= latest_bank;
                display_valid <= 1'b1;
            end
        end
    end
endmodule

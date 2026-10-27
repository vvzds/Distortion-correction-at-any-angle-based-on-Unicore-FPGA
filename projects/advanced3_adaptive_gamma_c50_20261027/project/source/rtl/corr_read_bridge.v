`timescale 1ns/1ps
// Correction-mode broker only: one pending command per client, one native
// burst in flight. Display priority at burst boundaries; never cross Column.
module corr_read_bridge #(parameter ADDR_BITS=28)(
    input wire clk, rst_n,
    input wire corr_rd_req,
    input wire [23:0] corr_rd_addr,
    input wire [6:0] corr_rd_len,
    output wire corr_rd_gnt, corr_rd_vld, corr_rd_last,
    output wire [255:0] corr_rd_data,
    input wire [ADDR_BITS-1:0] disp_araddr,
    input wire [3:0] disp_arlen,
    input wire disp_arvalid,
    output wire disp_arready, disp_rvalid,
    output wire [ADDR_BITS-1:0] axi_araddr,
    output wire [3:0] axi_arid, axi_arlen,
    output wire axi_arvalid,
    input wire axi_arready,
    input wire [255:0] axi_rdata,
    input wire axi_rvalid, axi_rlast,
    input wire [3:0] axi_rid
);
    reg corr_busy, disp_busy, waiting, owner_corr;
    reg [ADDR_BITS-1:0] corr_addr, disp_addr;
    reg [7:0] corr_issue, corr_return, disp_issue, disp_return;
    reg locked, locked_corr;
    wire choose_corr = locked ? locked_corr : !(disp_busy && disp_issue != 0);
    wire [7:0] remaining = choose_corr ? corr_issue : disp_issue;
    wire [ADDR_BITS-1:0] selected_addr = choose_corr ? corr_addr : disp_addr;
    wire [7:0] column_beats = 8'd128 - {1'b0,selected_addr[9:3]};
    wire [7:0] limited = remaining > 16 ? 8'd16 : remaining;
    wire [7:0] chunk = limited > column_beats ? column_beats : limited;
    wire address_ok = corr_rd_addr[2:0] == 0 && !corr_rd_addr[23];
    assign corr_rd_gnt = rst_n && !corr_busy && address_ok;
    assign disp_arready = rst_n && !disp_busy;
    assign axi_arvalid = rst_n && !waiting && remaining != 0 &&
                         (choose_corr ? corr_busy : disp_busy);
    assign axi_araddr = selected_addr;
    assign axi_arlen = chunk[3:0]-1'b1;
    assign axi_arid = choose_corr ? 4'd1 : 4'd0;
    assign disp_rvalid = rst_n && waiting && !owner_corr && axi_rvalid && axi_rid == 0;
    assign corr_rd_vld = rst_n && waiting && owner_corr && axi_rvalid && axi_rid == 1;
    assign corr_rd_data = axi_rdata;
    assign corr_rd_last = corr_rd_vld && corr_return == 1;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            corr_busy<=0; disp_busy<=0; waiting<=0; owner_corr<=0;
            corr_addr<=0; disp_addr<=0; corr_issue<=0; corr_return<=0;
            disp_issue<=0; disp_return<=0; locked<=0; locked_corr<=0;
        end else begin
            if (corr_rd_req && corr_rd_gnt) begin
                corr_busy<=1; corr_addr<=corr_rd_addr;
                corr_issue<={1'b0,corr_rd_len}+8'd1;
                corr_return<={1'b0,corr_rd_len}+8'd1;
            end
            if (disp_arvalid && disp_arready) begin
                disp_busy<=1; disp_addr<=disp_araddr;
                disp_issue<={4'd0,disp_arlen}+8'd1;
                disp_return<={4'd0,disp_arlen}+8'd1;
            end
            if (axi_arvalid && !axi_arready) begin
                locked<=1; locked_corr<=choose_corr;
            end
            if (axi_arvalid && axi_arready) begin
                locked<=0; waiting<=1; owner_corr<=choose_corr;
                if (choose_corr) begin
                    corr_issue<=corr_issue-chunk;
                    corr_addr<=corr_addr+({{(ADDR_BITS-8){1'b0}},chunk}<<3);
                end else begin
                    disp_issue<=disp_issue-chunk;
                    disp_addr<=disp_addr+({{(ADDR_BITS-8){1'b0}},chunk}<<3);
                end
            end
            if (corr_rd_vld) begin
                corr_return<=corr_return-1'b1;
                if (axi_rlast) waiting<=0;
                if (corr_rd_last) corr_busy<=0;
            end
            if (disp_rvalid) begin
                disp_return<=disp_return-1'b1;
                if (axi_rlast) waiting<=0;
                if (disp_return == 1) disp_busy<=0;
            end
        end
    end
endmodule

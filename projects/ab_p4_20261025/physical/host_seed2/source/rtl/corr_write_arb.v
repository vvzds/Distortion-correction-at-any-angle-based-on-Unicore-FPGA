`timescale 1ns/1ps
// Correction-mode Column splitter. Intermediate native LAST is hidden from
// the original writer. All data pulls retain original command ownership.
module corr_write_arb #(parameter ADDR_BITS=28)(
    input wire clk,rst_n,
    input wire [ADDR_BITS-1:0] raw_awaddr,
    input wire [3:0] raw_awlen,raw_awid,
    input wire raw_awvalid,
    output wire raw_awready,raw_wpull,raw_wlast,
    input wire [255:0] raw_wdata,
    input wire [31:0] raw_wstrb,
    input wire [23:0] corr_awaddr,
    input wire [3:0] corr_awlen,
    input wire corr_awvalid,
    output wire corr_awready,corr_wpull,corr_wlast,
    input wire [255:0] corr_wdata,
    output wire [ADDR_BITS-1:0] axi_awaddr,
    output wire [3:0] axi_awlen,axi_awid,
    output wire axi_awvalid,
    input wire axi_awready,
    output wire [255:0] axi_wdata,
    output wire [31:0] axi_wstrb,
    input wire axi_wpull,axi_wlast
);
    reg busy, waiting, owner_corr, locked, locked_corr;
    reg [ADDR_BITS-1:0] next_addr;
    reg [4:0] remaining;
    reg [3:0] saved_id;
    wire choose_corr=locked ? locked_corr : !raw_awvalid;
    wire [ADDR_BITS-1:0] first_addr=choose_corr ? {{(ADDR_BITS-24){1'b0}},corr_awaddr} : raw_awaddr;
    wire [4:0] first_beats={1'b0,(choose_corr ? corr_awlen : raw_awlen)}+5'd1;
    wire [ADDR_BITS-1:0] selected_addr=busy ? next_addr : first_addr;
    wire [7:0] column_beats=8'd128-{1'b0,selected_addr[9:3]};
    wire [4:0] count=busy ? remaining : first_beats;
    wire [4:0] chunk=count > column_beats ? column_beats[4:0] : count;
    assign axi_awvalid=rst_n && (busy ? (!waiting && remaining!=0) :
                                                  (choose_corr ? corr_awvalid : raw_awvalid));
    assign axi_awaddr=selected_addr;
    assign axi_awlen=chunk[3:0]-1'b1;
    assign axi_awid=busy ? saved_id : (choose_corr ? 4'd1 : raw_awid);
    assign raw_awready=rst_n && !busy && !choose_corr && axi_awready;
    assign corr_awready=rst_n && !busy && choose_corr && axi_awready;
    assign axi_wdata=owner_corr ? corr_wdata : raw_wdata;
    assign axi_wstrb=owner_corr ? 32'hffffffff : raw_wstrb;
    assign raw_wpull=rst_n && busy && waiting && !owner_corr && axi_wpull;
    assign raw_wlast=raw_wpull && axi_wlast && remaining==0;
    assign corr_wpull=rst_n && busy && waiting && owner_corr && axi_wpull;
    assign corr_wlast=corr_wpull && axi_wlast && remaining==0;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy<=0; waiting<=0; owner_corr<=0; locked<=0; locked_corr<=0;
            next_addr<=0; remaining<=0; saved_id<=0;
        end else begin
            if (axi_awvalid && !axi_awready && !busy) begin
                locked<=1; locked_corr<=choose_corr;
            end
            if (axi_awvalid && axi_awready) begin
                busy<=1; waiting<=1; locked<=0;
                remaining<=count-chunk;
                next_addr<=selected_addr+({{(ADDR_BITS-5){1'b0}},chunk}<<3);
                if (!busy) begin owner_corr<=choose_corr; saved_id<=axi_awid; end
            end
            if (busy && waiting && axi_wpull && axi_wlast) begin
                waiting<=0;
                if (remaining==0) busy<=0;
            end
        end
    end
endmodule

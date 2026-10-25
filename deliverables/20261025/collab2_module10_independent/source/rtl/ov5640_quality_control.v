`timescale 1ns/1ps
// 同时钟域封装。只在原初始化主机释放总线后接管；init_done应为已同步信号。
// scl_low/sda_low仅表示本主机下拉，顶层需开漏三态及外部上拉。
module ov5640_quality_control #(
    parameter HALF_CYCLES=675,
    parameter BUS_TIMEOUT=270000,
    parameter LOCK_TIMEOUT=25000000
)(
    input wire clk,input wire rst_n,input wire init_done,
    input wire start,input wire [1:0]cmd,
    output wire busy,output wire done,output wire error,
    output wire locked,output wire recovery_required,
    output wire snapshot_valid,output wire [119:0]snapshot,
    input wire scl_in,input wire sda_in,
    output wire scl_low,output wire sda_low
);
    wire req,ready,rd,rsp,rerr,abort_bus;
    wire [15:0]addr;
    wire [7:0]wdata,rdata;
    ov5640_quality_lock #(.TIMEOUT_CYCLES(LOCK_TIMEOUT)) u_lock(
      .clk(clk),.rst_n(rst_n),.init_done(init_done),.start(start),.cmd(cmd),
      .busy(busy),.done(done),.error(error),.abort_bus(abort_bus),.locked(locked),.recovery_required(recovery_required),
      .snapshot_valid(snapshot_valid),.snapshot(snapshot),
      .req_valid(req),.req_ready(ready),.req_read(rd),.req_addr(addr),.req_wdata(wdata),
      .rsp_valid(rsp),.rsp_error(rerr),.rsp_rdata(rdata));
    ov5640_sccb_access #(.HALF_CYCLES(HALF_CYCLES),.TIMEOUT_CYCLES(BUS_TIMEOUT)) u_bus(
      .clk(clk),.rst_n(rst_n && !abort_bus),.req_valid(req),.req_ready(ready),.req_read(rd),
      .req_addr(addr),.req_wdata(wdata),.rsp_valid(rsp),.rsp_error(rerr),.rsp_rdata(rdata),
      .scl_in(scl_in),.sda_in(sda_in),.scl_low(scl_low),.sda_low(sda_low));
endmodule

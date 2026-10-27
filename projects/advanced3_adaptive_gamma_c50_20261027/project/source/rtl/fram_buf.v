`include "source/rtl/video_contract.vh"
`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: Meyesemi
// Engineer: Nill
// 
// Create Date: 15/03/23 14:17:29
// Design Name: 
// Module Name: fram_buf
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////
`define UD #1
module fram_buf #(
    parameter [2:0] RD_SLOT_BASE = `VC_RD_SLOT_BASE,
    parameter                     MEM_ROW_WIDTH        = 15    ,
    parameter                     MEM_COLUMN_WIDTH     = 10    ,
    parameter                     MEM_BANK_WIDTH       = 3     ,
    parameter                     CTRL_ADDR_WIDTH = MEM_ROW_WIDTH + MEM_BANK_WIDTH + MEM_COLUMN_WIDTH,
    parameter                     MEM_DQ_WIDTH         = 32    ,
    parameter                     H_NUM                = `VC_WIDTH,//12'd1920,
    parameter                     V_NUM                = `VC_HEIGHT,//12'd1080,//12'd106,//
    parameter                     PIX_WIDTH            = `VC_PIXEL_BITS//24 
)(
    // Correction interfaces: DDR clock domain only, no board pins.
    output [1:0] o_frame_wcnt,
    output o_frame_update,
    input corr_src_hold_req,
    output corr_src_hold_gnt,
    output [1:0] corr_src_slot,
    input corr_src_rel,
    input corr_rd_req,
    input [23:0] corr_rd_addr,
    input [6:0] corr_rd_len,
    output corr_rd_gnt,corr_rd_vld,corr_rd_last,
    output [255:0] corr_rd_data,
    input corr_wr_req,
    input [23:0] corr_wr_addr,
    input [31:0] corr_wr_data,
    output corr_wr_gnt,
    input corr_wr_slot_req,
    output corr_wr_slot_gnt,
    output [2:0] corr_wr_slot,
    input corr_wr_commit,
    output corr_pub_pulse,
    output corr_protocol_error,
    input                         vin_clk,
    input                         wr_fsync,
    input                         wr_en,
    input  [PIX_WIDTH- 1'b1 : 0]  wr_data,
    output                        init_done,
    output                        frame_written,
    
    input                         ddr_clk,
    input                         ddr_rstn,
    
    input                         vout_clk,
    input                         rd_fsync,
    input                         rd_en,
    output                        vout_de,
    output [PIX_WIDTH- 1'b1 : 0]  vout_data,
    
    output [CTRL_ADDR_WIDTH-1:0]  axi_awaddr     ,
    output [3:0]                  axi_awid       ,
    output [3:0]                  axi_awlen      ,
    output [2:0]                  axi_awsize     ,
    output [1:0]                  axi_awburst    ,
    input                         axi_awready    ,
    output                        axi_awvalid    ,
                                                  
    output [MEM_DQ_WIDTH*8-1:0]   axi_wdata      ,
    output [MEM_DQ_WIDTH -1 :0]   axi_wstrb      ,
    input                         axi_wlast      ,
    output                        axi_wvalid     ,
    input                         axi_wready     ,
    input  [3 : 0]                axi_bid        ,                                      
                                                  
    output [CTRL_ADDR_WIDTH-1:0]  axi_araddr     ,
    output [3:0]                  axi_arid       ,
    output [3:0]                  axi_arlen      ,
    output [2:0]                  axi_arsize     ,
    output [1:0]                  axi_arburst    ,
    output                        axi_arvalid    ,
    input                         axi_arready    ,
                                                  
    output                        axi_rready     ,
    input  [MEM_DQ_WIDTH*8-1:0]   axi_rdata      ,
    input                         axi_rvalid     ,
    input                         axi_rlast      ,
    input  [3:0]                  axi_rid            
);
    parameter LEN_WIDTH       = 32;
    parameter LINE_ADDR_WIDTH = `VC_SLOT_WORD_BITS;//19;//1440 * 1080 = 1 555 200 = 21'h17BB00
    parameter FRAME_CNT_WIDTH = CTRL_ADDR_WIDTH - LINE_ADDR_WIDTH;
    
    wire                        ddr_wreq;     
    wire [CTRL_ADDR_WIDTH- 1'b1 : 0] ddr_waddr;    
    wire [LEN_WIDTH- 1'b1 : 0]  ddr_wr_len;   
    wire                        ddr_wrdy;     
    wire                        ddr_wdone;    
    wire [8*MEM_DQ_WIDTH-1 : 0] ddr_wdata;    
    wire                        ddr_wdata_req;
    
    wire                        rd_cmd_en   ;
    wire [CTRL_ADDR_WIDTH-1:0]  rd_cmd_addr ;
    wire [LEN_WIDTH- 1'b1: 0]   rd_cmd_len  ;
    wire                        rd_cmd_ready;
    wire                        rd_cmd_done;
                                
    wire                        read_ready  = 1'b1;
    wire [MEM_DQ_WIDTH*8-1:0]   read_rdata  ;
    wire                        read_en     ;
    wire                        ddr_wr_bac;

    localparam CORR_ENABLE = RD_SLOT_BASE == `VC_CORR_BASE;
    wire [1:0] write_bank, read_bank, raw_read_bank;
    wire raw_display_valid;
    wire [CTRL_ADDR_WIDTH-1:0] raw_awaddr,raw_araddr;
    wire [3:0] raw_awid,raw_awlen,raw_arid,raw_arlen;
    wire raw_awvalid,raw_awready,raw_wready,raw_wlast;
    wire raw_arvalid,raw_arready,raw_rvalid;
    wire [MEM_DQ_WIDTH*8-1:0] raw_wdata;
    wire [MEM_DQ_WIDTH-1:0] raw_wstrb;
    wire [3:0] raw_rid = 4'd0;

    wire write_frame_start, write_frame_complete, read_frame_start;
    assign frame_written = write_frame_complete;
    frame_bank_ctrl #(.CORR_ENABLE(CORR_ENABLE)) u_frame_banks (
        .clk(ddr_clk), .rst_n(ddr_rstn),
        .wr_start(write_frame_start), .wr_complete(write_frame_complete),
        .rd_start(read_frame_start && !CORR_ENABLE), .wr_bank(write_bank), .rd_bank(raw_read_bank),
        .o_frame_wcnt(o_frame_wcnt), .o_frame_update(o_frame_update),
        .corr_src_hold_req(corr_src_hold_req), .corr_src_hold_gnt(corr_src_hold_gnt),
        .corr_src_slot(corr_src_slot), .corr_src_rel(corr_src_rel),
        .display_valid(raw_display_valid)
    );
    wr_buf #(
        .ADDR_WIDTH       (  CTRL_ADDR_WIDTH  ),//parameter                     ADDR_WIDTH      = 6'd27,
        .ADDR_OFFSET      (  32'd0            ),//parameter                     ADDR_OFFSET     = 32'h0000_0000,
        .H_NUM            (  H_NUM            ),//parameter                     H_NUM           = `VC_WIDTH,
        .V_NUM            (  V_NUM            ),//parameter                     V_NUM           = `VC_HEIGHT,
        .DQ_WIDTH         (  MEM_DQ_WIDTH     ),//parameter                     DQ_WIDTH        = 7'd32,
        .LEN_WIDTH        (  LEN_WIDTH        ),//parameter                     LEN_WIDTH       = 6'd16,
        .PIX_WIDTH        (  PIX_WIDTH        ),//parameter                     PIX_WIDTH       = 6'd24,
        .LINE_ADDR_WIDTH  (  LINE_ADDR_WIDTH  ),//parameter                     LINE_ADDR_WIDTH = 4'd19,
        .FRAME_CNT_WIDTH  (  FRAME_CNT_WIDTH  ) //parameter                     FRAME_CNT_WIDTH = 4'd8
    ) wr_buf (                                       
        .ddr_clk          (  ddr_clk          ),//input                         ddr_clk,
        .ddr_rstn         (  ddr_rstn         ),//input                         ddr_rstn,
                                              
        .wr_clk           (  vin_clk          ),//input                         wr_clk,
        .wr_fsync         (  wr_fsync         ),
        .frame_bank       (  write_bank       ),
        .frame_start      (  write_frame_start ),
        .frame_complete   (  write_frame_complete ),//input                         wr_fsync,
        .wr_en            (  wr_en            ),//input                         wr_en,
        .wr_data          (  wr_data          ),//input  [PIX_WIDTH- 1'b1 : 0]  wr_data,
        
        .rd_bac           (  ddr_wr_bac       ),//input                         rd_bac,                                      
        .ddr_wreq         (  ddr_wreq         ),//output                        ddr_wreq,
        .ddr_waddr        (  ddr_waddr        ),//output [ADDR_WIDTH- 1'b1 : 0] ddr_waddr,
        .ddr_wr_len       (  ddr_wr_len       ),//output [LEN_WIDTH- 1'b1 : 0]  ddr_wr_len,
        .ddr_wrdy         (  ddr_wrdy         ),//input                         ddr_wrdy,
        .ddr_wdone        (  ddr_wdone        ),//input                         ddr_wdone,
        .ddr_wdata        (  ddr_wdata        ),//output [8*DQ_WIDTH- 1'b1 : 0] ddr_wdata,
        .ddr_wdata_req    (  ddr_wdata_req    ),//input                         ddr_wdata_req,
                                              
        .frame_wcnt       (                   ),//output [FRAME_CNT_WIDTH-1 :0] frame_wcnt,
        .frame_wirq       (  frame_wirq       ) //output                        frame_wirq
    );
    
    rd_buf #(
        .ADDR_WIDTH       (  CTRL_ADDR_WIDTH  ),//parameter                     ADDR_WIDTH      = 6'd27,
        .ADDR_OFFSET      (  {25'd0,RD_SLOT_BASE} << LINE_ADDR_WIDTH ),//parameter                     ADDR_OFFSET     = 32'h0000_0000,
        .H_NUM            (  H_NUM            ),//parameter                     H_NUM           = `VC_WIDTH,
        .V_NUM            (  V_NUM            ),//parameter                     V_NUM           = `VC_HEIGHT,
        .DQ_WIDTH         (  MEM_DQ_WIDTH     ),//parameter                     DQ_WIDTH        = 7'd32,
        .LEN_WIDTH        (  LEN_WIDTH        ),//parameter                     LEN_WIDTH       = 6'd16,
        .PIX_WIDTH        (  PIX_WIDTH        ),//parameter                     PIX_WIDTH       = 6'd24,
        .LINE_ADDR_WIDTH  (  LINE_ADDR_WIDTH  ),//parameter                     LINE_ADDR_WIDTH = 4'd19,
        .FRAME_CNT_WIDTH  (  FRAME_CNT_WIDTH  ) //parameter                     FRAME_CNT_WIDTH = 4'd8
    ) rd_buf (
        .ddr_clk         (  ddr_clk           ),//input                         ddr_clk,
        .ddr_rstn        (  ddr_rstn          ),//input                         ddr_rstn,

        .vout_clk        (  vout_clk          ),//input                         vout_clk,
        .rd_fsync        (  rd_fsync          ),
        .frame_bank      (  read_bank         ),
        .frame_start     (  read_frame_start  ),//input                         rd_fsync,
        .rd_en           (  rd_en             ),//input                         rd_en,
        .vout_de         (  vout_de           ),//output                        vout_de,
        .vout_data       (  vout_data         ),//output [PIX_WIDTH- 1'b1 : 0]  vout_data,
        
        .init_done       (  init_done         ),//input                         init_done,
      
        .ddr_rreq        (  rd_cmd_en         ),//output                        ddr_rreq,
        .ddr_raddr       (  rd_cmd_addr       ),//output [ADDR_WIDTH- 1'b1 : 0] ddr_raddr,
        .ddr_rd_len      (  rd_cmd_len        ),//output [LEN_WIDTH- 1'b1 : 0]  ddr_rd_len,
        .ddr_rrdy        (  rd_cmd_ready      ),//input                         ddr_rrdy,
        .ddr_rdone       (  rd_cmd_done       ),//input                         ddr_rdone,
                                              
        .ddr_rdata       (  read_rdata        ),//input [8*DQ_WIDTH- 1'b1 : 0]  ddr_rdata,
        .ddr_rdata_en    (  read_en           ) //input                         ddr_rdata_en,
    );
    
    wr_rd_ctrl_top#(
        .CTRL_ADDR_WIDTH  (  CTRL_ADDR_WIDTH  ),//parameter                    CTRL_ADDR_WIDTH      = 28,
        .MEM_DQ_WIDTH     (  MEM_DQ_WIDTH     ) //parameter                    MEM_DQ_WIDTH         = 16
    )wr_rd_ctrl_top (                         
        .clk              (  ddr_clk          ),//input                        clk            ,            
        .rstn             (  ddr_rstn         ),//input                        rstn           ,            
                                              
        .wr_cmd_en        (  ddr_wreq         ),//input                        wr_cmd_en   ,
        .wr_cmd_addr      (  ddr_waddr        ),//input  [CTRL_ADDR_WIDTH-1:0] wr_cmd_addr ,
        .wr_cmd_len       (  ddr_wr_len       ),//input  [31£º0]               wr_cmd_len  ,
        .wr_cmd_ready     (  ddr_wrdy         ),//output                       wr_cmd_ready,
        .wr_cmd_done      (  ddr_wdone        ),//output                       wr_cmd_done,
        .wr_bac           (  ddr_wr_bac       ),//output                       wr_bac,                                     
        .wr_ctrl_data     (  ddr_wdata        ),//input  [MEM_DQ_WIDTH*8-1:0]  wr_ctrl_data,
        .wr_data_re       (  ddr_wdata_req    ),//output                       wr_data_re  ,
                                              
        .rd_cmd_en        (  rd_cmd_en        ),//input                        rd_cmd_en   ,
        .rd_cmd_addr      (  rd_cmd_addr      ),//input  [CTRL_ADDR_WIDTH-1:0] rd_cmd_addr ,
        .rd_cmd_len       (  rd_cmd_len       ),//input  [31£º0]               rd_cmd_len  ,
        .rd_cmd_ready     (  rd_cmd_ready     ),//output                       rd_cmd_ready, 
        .rd_cmd_done      (  rd_cmd_done      ),//output                       rd_cmd_done,
                                              
        .read_ready       (  read_ready       ),//input                        read_ready  ,    
        .read_rdata       (  read_rdata       ),//output [MEM_DQ_WIDTH*8-1:0]  read_rdata  ,    
        .read_en          (  read_en          ),//output                       read_en     ,                                          
        // write channel                        
        .axi_awaddr       (  raw_awaddr       ),//output [CTRL_ADDR_WIDTH-1:0] axi_awaddr     ,  
        .axi_awid         (  raw_awid         ),//output [3:0]                 axi_awid       ,
        .axi_awlen        (  raw_awlen        ),//output [3:0]                 axi_awlen      ,
        .axi_awsize       (  axi_awsize       ),//output [2:0]                 axi_awsize     ,
        .axi_awburst      (  axi_awburst      ),//output [1:0]                 axi_awburst    , //only support 2'b01: INCR
        .axi_awready      (  raw_awready      ),//input                        axi_awready    ,
        .axi_awvalid      (  raw_awvalid      ),//output                       axi_awvalid    ,
                                              
        .axi_wdata        (  raw_wdata        ),//output [MEM_DQ_WIDTH*8-1:0]  axi_wdata      ,
        .axi_wstrb        (  raw_wstrb        ),//output [MEM_DQ_WIDTH -1 :0]  axi_wstrb      ,
        .axi_wlast        (  raw_wlast        ),//output                       axi_wlast      ,
        .axi_wvalid       (  axi_wvalid       ),//output                       axi_wvalid     ,
        .axi_wready       (  raw_wready       ),//input                        axi_wready     ,
        .axi_bid          (  4'd0             ),//input  [3 : 0]               axi_bid        , // Master Interface Write Response.
        .axi_bresp        (  2'd0             ),//input  [1 : 0]               axi_bresp      , // Write response. This signal indicates the status of the write transaction.
        .axi_bvalid       (  1'b0             ),//input                        axi_bvalid     , // Write response valid. This signal indicates that the channel is signaling a valid write response.
        .axi_bready       (                   ),//output                       axi_bready     ,
                                              
        // read channel                          
        .axi_araddr       (  raw_araddr       ),//output [CTRL_ADDR_WIDTH-1:0] axi_araddr     ,    
        .axi_arid         (  raw_arid         ),//output [3:0]                 axi_arid       ,
        .axi_arlen        (  raw_arlen        ),//output [3:0]                 axi_arlen      ,
        .axi_arsize       (  axi_arsize       ),//output [2:0]                 axi_arsize     ,
        .axi_arburst      (  axi_arburst      ),//output [1:0]                 axi_arburst    ,
        .axi_arvalid      (  raw_arvalid      ),//output                       axi_arvalid    , 
        .axi_arready      (  raw_arready      ),//input                        axi_arready    , //only support 2'b01: INCR
                                              
        .axi_rready       (  axi_rready       ),//output                       axi_rready     ,
        .axi_rdata        (  axi_rdata        ),//input  [MEM_DQ_WIDTH*8-1:0]  axi_rdata      ,
        .axi_rvalid       (  raw_rvalid       ),//input                        axi_rvalid     ,
        .axi_rlast        (  axi_rlast        ),//input                        axi_rlast      ,
        .axi_rid          (  raw_rid          ),//input  [3:0]                 axi_rid        ,
        .axi_rresp        (  2'd0             ) //input  [1:0]                 axi_rresp      
    );


    generate if (!CORR_ENABLE) begin : g_bypass
        // Compile-time direct wiring preserves the verified native traffic.
        assign read_bank=raw_read_bank;
        assign init_done=raw_display_valid;
        assign axi_awaddr=raw_awaddr; assign axi_awid=raw_awid;
        assign axi_awlen=raw_awlen; assign axi_awvalid=raw_awvalid;
        assign raw_awready=axi_awready;
        assign axi_wdata=raw_wdata; assign axi_wstrb=raw_wstrb;
        assign raw_wlast=axi_wlast; assign raw_wready=axi_wready;
        assign axi_araddr=raw_araddr; assign axi_arid=raw_arid;
        assign axi_arlen=raw_arlen; assign axi_arvalid=raw_arvalid;
        assign raw_arready=axi_arready; assign raw_rvalid=axi_rvalid;
        assign corr_rd_gnt=0; assign corr_rd_vld=0; assign corr_rd_last=0;
        assign corr_rd_data=0; assign corr_wr_gnt=0; assign corr_wr_slot_gnt=0;
        assign corr_wr_slot=0; assign corr_pub_pulse=0; assign corr_protocol_error=0;
    end else begin : g_correction
        wire writer_idle,publish;
        wire [23:0] cw_awaddr;
        wire [3:0] cw_awlen;
        wire cw_awvalid,cw_awready,cw_wpull,cw_wlast;
        wire [255:0] cw_wdata;
        assign corr_pub_pulse=publish;
        corr_slot_ctrl u_corr_slots (
            .clk(ddr_clk),.rst_n(ddr_rstn),.rd_start(read_frame_start),
            .corr_wr_slot_req(corr_wr_slot_req),.writer_idle(writer_idle),.publish(publish),
            .corr_wr_slot_gnt(corr_wr_slot_gnt),.corr_wr_slot(corr_wr_slot),
            .rd_bank(read_bank),.display_valid(init_done)
        );
        corr_read_bridge #(.ADDR_BITS(CTRL_ADDR_WIDTH)) u_corr_read (
            .clk(ddr_clk),.rst_n(ddr_rstn),
            .corr_rd_req(corr_rd_req),.corr_rd_addr(corr_rd_addr),.corr_rd_len(corr_rd_len),
            .corr_rd_gnt(corr_rd_gnt),.corr_rd_vld(corr_rd_vld),
            .corr_rd_data(corr_rd_data),.corr_rd_last(corr_rd_last),
            .disp_araddr(raw_araddr),.disp_arlen(raw_arlen),.disp_arvalid(raw_arvalid),
            .disp_arready(raw_arready),.disp_rvalid(raw_rvalid),
            .axi_araddr(axi_araddr),.axi_arid(axi_arid),.axi_arlen(axi_arlen),
            .axi_arvalid(axi_arvalid),.axi_arready(axi_arready),
            .axi_rdata(axi_rdata),.axi_rvalid(axi_rvalid),.axi_rlast(axi_rlast),.axi_rid(axi_rid)
        );
        corr_write_pack #(.FRAME_WORDS(H_NUM*V_NUM/2),.SLOT_BITS(LINE_ADDR_WIDTH)) u_corr_pack (
            .clk(ddr_clk),.rst_n(ddr_rstn),.begin_frame(corr_wr_slot_gnt),.frame_slot(corr_wr_slot),
            .corr_wr_req(corr_wr_req),.corr_wr_addr(corr_wr_addr),.corr_wr_data(corr_wr_data),
            .corr_wr_gnt(corr_wr_gnt),.corr_wr_commit(corr_wr_commit),
            .frame_idle(writer_idle),.publish(publish),.protocol_error(corr_protocol_error),
            .awaddr(cw_awaddr),.awlen(cw_awlen),.awvalid(cw_awvalid),.awready(cw_awready),
            .wdata(cw_wdata),.wpull(cw_wpull),.wlast(cw_wlast)
        );
        corr_write_arb #(.ADDR_BITS(CTRL_ADDR_WIDTH)) u_corr_write (
            .clk(ddr_clk),.rst_n(ddr_rstn),
            .raw_awaddr(raw_awaddr),.raw_awid(raw_awid),.raw_awlen(raw_awlen),
            .raw_awvalid(raw_awvalid),.raw_awready(raw_awready),
            .raw_wdata(raw_wdata),.raw_wstrb(raw_wstrb),.raw_wpull(raw_wready),.raw_wlast(raw_wlast),
            .corr_awaddr(cw_awaddr),.corr_awlen(cw_awlen),.corr_awvalid(cw_awvalid),.corr_awready(cw_awready),
            .corr_wdata(cw_wdata),.corr_wpull(cw_wpull),.corr_wlast(cw_wlast),
            .axi_awaddr(axi_awaddr),.axi_awlen(axi_awlen),.axi_awid(axi_awid),.axi_awvalid(axi_awvalid),
            .axi_awready(axi_awready),.axi_wdata(axi_wdata),.axi_wstrb(axi_wstrb),
            .axi_wpull(axi_wready),.axi_wlast(axi_wlast)
        );
    end endgenerate

endmodule

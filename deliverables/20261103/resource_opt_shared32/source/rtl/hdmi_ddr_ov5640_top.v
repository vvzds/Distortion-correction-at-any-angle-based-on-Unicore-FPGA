`include "source/rtl/video_contract.vh"
`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company:Meyesemi 
// Engineer: Will
// 
// Create Date: 2023-03-17  
// Design Name:  
// Module Name: 
// Project Name: 
// Target Devices: Pango
// Tool Versions: 
// Description: 
//      
// Dependencies: 
// 
// Revision:
// Revision 1.0 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////
`define UD #1
// Board top: CMOS2 RAW8 -> Bayer interpolation -> DDR3 correction/frame store
// -> display-only denoise -> sharpen -> optional calibration OSD -> HDMI.
// BNO085 SPI and host UART use the 125 MHz control domain; filters/OSD use the
// 74.25 MHz 1080p30 pixel domain. Four added pixel clocks do not add DDR traffic.

module hdmi_ddr_ov5640_top#(
	parameter MEM_ROW_ADDR_WIDTH   = 15         ,
	parameter MEM_COL_ADDR_WIDTH   = 10         ,
	parameter MEM_BADDR_WIDTH      = 3          ,
	parameter MEM_DQ_WIDTH         =  32        ,
	parameter MEM_DQS_WIDTH        =  32/8,
    parameter [2:0] RD_SLOT_BASE = `VC_RD_SLOT_BASE,
    parameter [1:0] BAYER_PHASE = 2'd0
)(
	input                                sys_clk              ,//27MHz board oscillator
    input                                uart_rx,
    input                                key0_n,key1_n,key2_n,key3_n,key4_n,
    input                                bno_miso,bno_int_n,
    output                               bno_sck,bno_mosi,bno_cs_n,bno_rst_n,bno_wake_n,
    output                               uart_tx,
    input                                clk_p ,
    input                                clk_n ,
//OV5640
    output  [1:0]                        cmos_init_done       ,//OV5640寄存器初始化完成
    //coms1	
    inout                                cmos1_scl            ,//cmos1 i2c 
    inout                                cmos1_sda            ,//cmos1 i2c 
    input                                cmos1_vsync          ,//cmos1 vsync
    input                                cmos1_href           ,//cmos1 hsync refrence,data valid
    input                                cmos1_pclk           ,//cmos1 pxiel clock
    input   [7:0]                        cmos1_data           ,//cmos1 data
    output                               cmos1_reset          ,//cmos1 reset
    //coms2
    inout                                cmos2_scl            ,//cmos2 i2c 
    inout                                cmos2_sda            ,//cmos2 i2c 
    input                                cmos2_vsync          ,//cmos2 vsync
    input                                cmos2_href           ,//cmos2 hsync refrence,data valid
    input                                cmos2_pclk           ,//cmos2 pxiel clock
    input   [7:0]                        cmos2_data           ,//cmos2 data
    output                               cmos2_reset          ,//cmos2 reset
//DDR
    output                               mem_rst_n                 ,
    output                               mem_ck                    ,
    output                               mem_ck_n                  ,
    output                               mem_cke                   ,
    output                               mem_cs_n                  ,
    output                               mem_ras_n                 ,
    output                               mem_cas_n                 ,
    output                               mem_we_n                  ,
    output                               mem_odt                   ,
    output      [MEM_ROW_ADDR_WIDTH-1:0] mem_a                     ,
    output      [MEM_BADDR_WIDTH-1:0]    mem_ba                    ,
    inout       [MEM_DQ_WIDTH/8-1:0]     mem_dqs                   ,
    inout       [MEM_DQ_WIDTH/8-1:0]     mem_dqs_n                 ,
    inout       [MEM_DQ_WIDTH-1:0]       mem_dq                    ,
    output      [MEM_DQ_WIDTH/8-1:0]     mem_dm                    ,
    output reg                           heart_beat_led            ,
    output                               ddr_init_done             ,
//MS72xx       
    output                               rstn_out                  ,
    output                               iic_tx_scl                ,
    inout                                iic_tx_sda                ,
    output [2:0]                         video_debug_led, // Unused board LEDs 5/6/7 held off
    output                               hdmi_int_led              ,//HDMI_OUT初始化完成
//HDMI_OUT
    output                               pix_clk                   ,//pixclk                           
    output     reg                       vs_out                    , 
    output     reg                       hs_out                    , 
    output     reg                       de_out                    ,
    output     reg[7:0]                  r_out                     , 
    output     reg[7:0]                  g_out                     , 
    output     reg[7:0]                  b_out         
);
/////////////////////////////////////////////////////////////////////////////////////
// ENABLE_DDR
    parameter CTRL_ADDR_WIDTH = MEM_ROW_ADDR_WIDTH + MEM_BADDR_WIDTH + MEM_COL_ADDR_WIDTH;//28
    parameter TH_1S = 27'd33000000;
/////////////////////////////////////////////////////////////////////////////////////
    reg  [15:0]                 rstn_1ms            ;
    wire                        cmos_scl            ;//cmos i2c clock
    wire                        cmos_sda            ;//cmos i2c data
    wire                        cmos_vsync          ;//cmos vsync
    wire                        cmos_href           ;//cmos hsync refrence,data valid
    wire                        cmos_pclk           ;//cmos pxiel clock
    wire   [7:0]                cmos_data           ;//cmos data
    wire                        cmos_reset          ;//cmos reset
    wire                        initial_en          ;
    wire[15:0]                  cmos1_d_16bit       ;
    wire                        cmos1_href_16bit    ;
    reg [7:0]                   cmos1_d_d0          ;
    reg                         cmos1_href_d0       ;
    reg                         cmos1_vsync_d0      ;
    wire                        cmos1_pclk_16bit    ;
    reg [7:0]                   cmos2_d_d0          /*synthesis PAP_MARK_DEBUG="1"*/;
    reg                         cmos2_href_d0       /*synthesis PAP_MARK_DEBUG="1"*/;
    reg                         cmos2_vsync_d0      /*synthesis PAP_MARK_DEBUG="1"*/;
    wire[15:0]                  o_rgb565            ;
    wire                        pclk_in_test        ;    
    wire                        vs_in_test          ;
    wire                        de_in_test          ;
    wire[15:0]                  i_rgb565   /*synthesis PAP_MARK_DEBUG="1"*/         ;
    wire                        de_re               ;
    wire                        core_clk;
    wire                        hs_o;
//axi bus   
    wire [CTRL_ADDR_WIDTH-1:0]  axi_awaddr                 ;
    wire                        axi_awuser_ap              ;
    wire [3:0]                  axi_awuser_id              ;
    wire [3:0]                  axi_awlen                  ;
    wire                        axi_awready                ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire                        axi_awvalid                ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire [MEM_DQ_WIDTH*8-1:0]   axi_wdata                  ;
    wire [MEM_DQ_WIDTH*8/8-1:0] axi_wstrb                  ;
    wire                        axi_wready                 ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire [3:0]                  axi_wusero_id              ;
    wire                        axi_wusero_last            ;
    wire [CTRL_ADDR_WIDTH-1:0]  axi_araddr                 ;
    wire                        axi_aruser_ap              ;
    wire [3:0]                  axi_aruser_id              ;
    wire [3:0]                  axi_arlen                  ;
    wire                        axi_arready                ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire                        axi_arvalid                ;/*synthesis PAP_MARK_DEBUG="1"*/
    wire [MEM_DQ_WIDTH*8-1:0]   axi_rdata                   /* synthesis syn_keep = 1 */;
    wire                        axi_rvalid                  /* synthesis syn_keep = 1 */;
    wire [3:0]                  axi_rid                    ;
    wire                        axi_rlast                  ;
    reg  [26:0]                 cnt                        ;
    reg  [15:0]                 cnt_1                      ;
/////////////////////////////////////////////////////////////////////////////////////
//PLL

    pll u_pll (
        .clkin1   (  sys_clk    ),//27MHz
        .clkout0  (  pix_clk    ),//74.25MHz, 1920x1080p30
        .clkout1  (  cfg_clk    ),//10MHz
        .clkout2  (  clk_25M    ),//25M
        .lock (  locked     )
    );

//配置7210
wire init_over_tx;
    ms72xx_ctl ms72xx_ctl(
        .clk             (  cfg_clk        ), //input       clk,
        .rst_n           (  rstn_out       ), //input       rstn,
        .init_over    (  init_over_tx   ), //output      init_over,                                
        .init_over_rx    (  init_over_rx   ), //output      init_over,
//        .iic_tx_scl      (  iic_tx_scl     ), //output      iic_scl,
//        .iic_tx_sda      (  iic_tx_sda     ), //inout       iic_sda
        .iic_scl         (  iic_tx_scl        ), //output      iic_scl,
        .iic_sda         (  iic_tx_sda        )  //inout       iic_sda
    );
//   assign    hdmi_int_led    =    init_over_tx; 
    
    always @(posedge cfg_clk)
    begin
    	if(!locked)
    	    rstn_1ms <= 16'd0;
    	else
    	begin
    		if(rstn_1ms == 16'h2710)
    		    rstn_1ms <= rstn_1ms;
    		else
    		    rstn_1ms <= rstn_1ms + 1'b1;
    	end
    end
    
    assign rstn_out = (rstn_1ms == 16'h2710);

//配置CMOS///////////////////////////////////////////////////////////////////////////////////
//OV5640 register configure enable    
    power_on_delay	power_on_delay_inst(
    	.clk_50M                 (sys_clk        ),//input
    	.reset_n                 (locked          ),//input	
    	.camera1_rstn            (cmos1_reset    ),//output
    	.camera2_rstn            (cmos2_reset    ),//output	
    	.camera_pwnd             (               ),//output
    	.initial_en              (initial_en     ) //output		
    );
//CMOS1 Camera 
    reg_config	coms1_reg_config(
    	.clk_25M                 (clk_25M            ),//input
    	.camera_rstn             (cmos1_reset        ),//input
    	.initial_en              (initial_en         ),//input		
    	.i2c_sclk                (cmos1_scl          ),//output
    	.i2c_sdat                (cmos1_sda          ),//inout
    	.reg_conf_done           (cmos_init_done[0]  ),//output config_finished
    	.reg_index               (                   ),//output reg [8:0]
    	.clock_20k               (                   ) //output reg
    );

//CMOS2 Camera 
    reg_config	coms2_reg_config(
    	.clk_25M                 (clk_25M            ),//input
    	.camera_rstn             (cmos2_reset        ),//input
    	.initial_en              (initial_en         ),//input		
    	.i2c_sclk                (cmos2_scl          ),//output
    	.i2c_sdat                (cmos2_sda          ),//inout
    	.reg_conf_done           (cmos_init_done[1]  ),//output config_finished
    	.reg_index               (                   ),//output reg [8:0]
    	.clock_20k               (                   ) //output reg
    );
// RAW8 camera capture. The module's 24 MHz oscillator feeds OV5640 XVCLK.
    wire raw2_vs;
    wire raw2_de;
    wire [15:0] raw2_rgb;
    reg [1:0] cmos2_cfg_sync;
    always @(posedge cmos2_pclk) begin
        cmos2_cfg_sync <= {cmos2_cfg_sync[0], cmos_init_done[1]};
        cmos2_d_d0 <= cmos2_data;
        cmos2_href_d0 <= cmos2_href;
        cmos2_vsync_d0 <= cmos2_vsync;
    end
    raw8_to_rgb565 #(.WIDTH(`VC_WIDTH), .HEIGHT(`VC_HEIGHT), .BAYER_PHASE(BAYER_PHASE)) u_raw2_rgb (
        .pclk(cmos2_pclk), .rst_n(cmos2_cfg_sync[1]),
        .vs_in(cmos2_vsync_d0), .de_in(cmos2_href_d0), .raw_in(cmos2_d_d0),
        .vs_out(raw2_vs), .de_out(raw2_de), .rgb_out(raw2_rgb)
    );
    assign pclk_in_test = cmos2_pclk;
    assign vs_in_test = raw2_vs;
    assign de_in_test = raw2_de;
    assign i_rgb565 = raw2_rgb;
    assign hdmi_int_led = init_over_tx;
    // Diagnostic overlay, monitor and SCCB readback removed.
    assign video_debug_led = 3'b000;

    // Contract mounting point, all signals in the 125 MHz DDR domain.
    wire corr_clk = core_clk;
    reg [1:0] corr_reset_sync;
    always @(posedge core_clk or negedge ddr_init_done)
        if(!ddr_init_done) corr_reset_sync<=0;
        else corr_reset_sync<={corr_reset_sync[0],1'b1};
    wire corr_rst_n = corr_reset_sync[1];
    wire [1:0] o_frame_wcnt;
    wire o_frame_update;
    wire corr_src_hold_req,corr_src_hold_gnt,corr_src_rel;
    wire [1:0] corr_src_slot;
    wire corr_rd_req,corr_rd_gnt,corr_rd_vld,corr_rd_last;
    wire [23:0] corr_rd_addr;
    wire [6:0] corr_rd_len;
    wire [255:0] corr_rd_data;
    wire corr_wr_req,corr_wr_gnt,corr_wr_slot_req,corr_wr_slot_gnt,corr_wr_commit;
    wire [23:0] corr_wr_addr;
    wire [31:0] corr_wr_data;
    wire [2:0] corr_wr_slot;
    wire corr_pub_pulse,corr_protocol_error;
    `include "source/rtl/correction_hook.vh"
    assign board_key_n={key4_n,key3_n,key2_n,key1_n,key0_n};

    fram_buf #(
        .RD_SLOT_BASE(RD_SLOT_BASE),
        .H_NUM(`VC_WIDTH), .V_NUM(`VC_HEIGHT), .PIX_WIDTH(`VC_PIXEL_BITS),
        .CTRL_ADDR_WIDTH(CTRL_ADDR_WIDTH), .MEM_DQ_WIDTH(MEM_DQ_WIDTH)
    ) fram_buf(
        .o_frame_wcnt(o_frame_wcnt),.o_frame_update(o_frame_update),
        .corr_src_hold_req(corr_src_hold_req),.corr_src_hold_gnt(corr_src_hold_gnt),.corr_src_slot(corr_src_slot),.corr_src_rel(corr_src_rel),
        .corr_rd_req(corr_rd_req),.corr_rd_addr(corr_rd_addr),.corr_rd_len(corr_rd_len),
        .corr_rd_gnt(corr_rd_gnt),.corr_rd_vld(corr_rd_vld),.corr_rd_last(corr_rd_last),.corr_rd_data(corr_rd_data),
        .corr_wr_req(corr_wr_req),.corr_wr_addr(corr_wr_addr),.corr_wr_data(corr_wr_data),.corr_wr_gnt(corr_wr_gnt),
        .corr_wr_slot_req(corr_wr_slot_req),.corr_wr_slot_gnt(corr_wr_slot_gnt),.corr_wr_slot(corr_wr_slot),
        .corr_wr_commit(corr_wr_commit),.corr_pub_pulse(corr_pub_pulse),.corr_protocol_error(corr_protocol_error),

        .ddr_clk        (  core_clk             ),//input                         ddr_clk,
        .ddr_rstn       (  ddr_init_done        ),//input                         ddr_rstn,
        //data_in                                  
        .vin_clk        (  pclk_in_test         ),//input                         vin_clk,
        .wr_fsync       (  vs_in_test           ),//input                         wr_fsync,
        .wr_en          (  de_in_test           ),//input                         wr_en,
        .wr_data        (  i_rgb565             ),//input  [15 : 0]  wr_data,
        //data_out
        .vout_clk       (  pix_clk              ),//input                         vout_clk,
        .rd_fsync       (  vs_o               ),//input                         rd_fsync,
        .rd_en          (  de_re                ),//input                         rd_en,
        .vout_de        (  de_o               ),//output                        vout_de,
        .vout_data      (  o_rgb565             ),//output [PIX_WIDTH- 1'b1 : 0]  vout_data,
        .frame_written  (                       ),
        .init_done      (  init_done            ),//output reg                    init_done,
        //axi bus
        .axi_awaddr     (  axi_awaddr           ),// output[27:0]
        .axi_awid       (  axi_awuser_id        ),// output[3:0]
        .axi_awlen      (  axi_awlen            ),// output[3:0]
        .axi_awsize     (                       ),// output[2:0]
        .axi_awburst    (                       ),// output[1:0]
        .axi_awready    (  axi_awready          ),// input
        .axi_awvalid    (  axi_awvalid          ),// output               
        .axi_wdata      (  axi_wdata            ),// output[255:0]
        .axi_wstrb      (  axi_wstrb            ),// output[31:0]
        .axi_wlast      (  axi_wusero_last      ),// input
        .axi_wvalid     (                       ),// output
        .axi_wready     (  axi_wready           ),// input
        .axi_bid        (  4'd0                 ),// input[3:0]
        .axi_araddr     (  axi_araddr           ),// output[27:0]
        .axi_arid       (  axi_aruser_id        ),// output[3:0]
        .axi_arlen      (  axi_arlen            ),// output[3:0]
        .axi_arsize     (                       ),// output[2:0]
        .axi_arburst    (                       ),// output[1:0]
        .axi_arvalid    (  axi_arvalid          ),// output
        .axi_arready    (  axi_arready          ),// input
        .axi_rready     (                       ),// output
        .axi_rdata      (  axi_rdata            ),// input[255:0]
        .axi_rvalid     (  axi_rvalid           ),// input
        .axi_rlast      (  axi_rlast            ),// input
        .axi_rid        (  axi_rid              ) // input[3:0]         
    );

     reg [1:0] display_ready;
     always @(posedge pix_clk) begin
        if (!ddr_init_done) display_ready <= 2'b00;
        else display_ready <= {display_ready[0], init_done};
     end
     // The quality filters are post-DDR display stages: they cannot change the
     // corrected frame contents, camera capture, publication rate, or DDR traffic.
     wire [15:0] denoised_rgb565,enhanced_rgb565;
     wire denoised_de,denoised_hs,denoised_vs;
     wire enhanced_de,enhanced_hs,enhanced_vs;
     wire [23:0] quality_rgb = {enhanced_rgb565[15:11],enhanced_rgb565[15:13],
                                enhanced_rgb565[10:5],enhanced_rgb565[10:9],
                                enhanced_rgb565[4:0],enhanced_rgb565[4:2]};
     wire [11:0] osd_x,osd_y;
     reg [11:0] osd_x_d0,osd_x_d1,osd_x_d2,osd_x_d3;
     reg [11:0] osd_y_d0,osd_y_d1,osd_y_d2,osd_y_d3;
     display_denoise u_display_denoise(
         .pix_clk(pix_clk),.pix_rst_n(ddr_init_done),.level_core(denoise_level),
         .rgb_in(display_ready[1] ? o_rgb565 : 16'd0),
         .de_in(de_o),.hs_in(hs_o),.vs_in(vs_o),
         .rgb_out(denoised_rgb565),.de_out(denoised_de),
         .hs_out(denoised_hs),.vs_out(denoised_vs));
     display_sharpen u_display_sharpen(
         .pix_clk(pix_clk),.pix_rst_n(ddr_init_done),.level_core(sharpen_level),
         .rgb_in(denoised_rgb565),
         .de_in(denoised_de),.hs_in(denoised_hs),.vs_in(denoised_vs),
         .rgb_out(enhanced_rgb565),.de_out(enhanced_de),
         .hs_out(enhanced_hs),.vs_out(enhanced_vs));
     always @(posedge pix_clk) begin
         osd_x_d0<=osd_x; osd_x_d1<=osd_x_d0; osd_x_d2<=osd_x_d1; osd_x_d3<=osd_x_d2;
         osd_y_d0<=osd_y; osd_y_d1<=osd_y_d0; osd_y_d2<=osd_y_d1; osd_y_d3<=osd_y_d2;
     end
     wire [23:0] osd_rgb;
     video_osd u_video_osd(
         .core_clk(core_clk),.core_rst_n(corr_rst_n),
         .row_valid(osd_row_valid),.row_index(osd_row_index),
         .row_data(osd_row_data),.enable(key_osd_visible),
         .pix_clk(pix_clk),.pix_rst_n(ddr_init_done),
         .x(osd_x_d3),.y(osd_y_d3),.de(enhanced_de),.vs(enhanced_vs),
         .rgb_in(quality_rgb),.rgb_out(osd_rgb));
     wire [23:0] display_rgb = enhanced_de ? osd_rgb : 24'd0;
     always@(posedge pix_clk) begin
        r_out <= display_rgb[23:16];
        g_out <= display_rgb[15:8];
        b_out <= display_rgb[7:0];
        vs_out<=enhanced_vs;
        hs_out<=enhanced_hs;
        de_out<=enhanced_de;
     end
/////////////////////////////////////////////////////////////////////////////////////
//产生visa时序 
     sync_vg sync_vg(                            
        .clk            (  pix_clk              ),//input                   clk,                                 
        .rstn           (  ddr_init_done            ),//input                   rstn,                            
        .vs_out         (  vs_o                 ),//output reg              vs_out,                                                                                                                                      
        .hs_out         (  hs_o                 ),//output reg              hs_out,            
        .de_out         (                           ),// nominal active area
        .de_re          (  de_re                    ), // read two clocks early
        .x_act          (  osd_x                    ),
        .y_act          (  osd_y                    )
    );  
////////////////////////////////////////////////////////////////////////////////////////////
//ddr    
/*        ddr3_100h ddr3_100h (
             .ref_clk                   (sys_clk            ),
             .resetn                    (rstn_out           ),// input
             .ddr_init_done             (ddr_init_done      ),// output
             .ddrphy_clkin              (core_clk           ),// output
             .pll_lock                  (pll_lock           ),// output

             .axi_awaddr                (axi_awaddr         ),// input [27:0]
             .axi_awuser_ap             (1'b0               ),// input
             .axi_awuser_id             (axi_awuser_id      ),// input [3:0]
             .axi_awlen                 (axi_awlen          ),// input [3:0]
             .axi_awready               (axi_awready        ),// output
             .axi_awvalid               (axi_awvalid        ),// input
             .axi_wdata                 (axi_wdata          ),
             .axi_wstrb                 (axi_wstrb          ),// input [31:0]
             .axi_wready                (axi_wready         ),// output
             .axi_wusero_id             (                   ),// output [3:0]
             .axi_wusero_last           (axi_wusero_last    ),// output
             .axi_araddr                (axi_araddr         ),// input [27:0]
             .axi_aruser_ap             (1'b0               ),// input
             .axi_aruser_id             (axi_aruser_id      ),// input [3:0]
             .axi_arlen                 (axi_arlen          ),// input [3:0]
             .axi_arready               (axi_arready        ),// output
             .axi_arvalid               (axi_arvalid        ),// input
             .axi_rdata                 (axi_rdata          ),// output [255:0]
             .axi_rid                   (axi_rid            ),// output [3:0]
             .axi_rlast                 (axi_rlast          ),// output
             .axi_rvalid                (axi_rvalid         ),// output

             .apb_clk                   (1'b0               ),// input
             .apb_rst_n                 (1'b1               ),// input
             .apb_sel                   (1'b0               ),// input
             .apb_enable                (1'b0               ),// input
             .apb_addr                  (8'b0               ),// input [7:0]
             .apb_write                 (1'b0               ),// input
             .apb_ready                 (                   ), // output
             .apb_wdata                 (16'b0              ),// input [15:0]
             .apb_rdata                 (                   ),// output [15:0]
             .apb_int                   (                   ),// output

             .mem_rst_n                 (mem_rst_n          ),// output
             .mem_ck                    (mem_ck             ),// output
             .mem_ck_n                  (mem_ck_n           ),// output
             .mem_cke                   (mem_cke            ),// output
             .mem_cs_n                  (mem_cs_n           ),// output
             .mem_ras_n                 (mem_ras_n          ),// output
             .mem_cas_n                 (mem_cas_n          ),// output
             .mem_we_n                  (mem_we_n           ),// output
             .mem_odt                   (mem_odt            ),// output
             .mem_a                     (mem_a              ),// output [14:0]
             .mem_ba                    (mem_ba             ),// output [2:0]
             .mem_dqs                   (mem_dqs            ),// inout [3:0]
             .mem_dqs_n                 (mem_dqs_n          ),// inout [3:0]
             .mem_dq                    (mem_dq             ),// inout [31:0]
             .mem_dm                    (mem_dm             ),// output [3:0]
             //debug
             .debug_data                (                   ),// output [135:0]
             .debug_slice_state         (                   ),// output [51:0]
             .debug_calib_ctrl          (                   ),// output [21:0]
             .ck_dly_set_bin            (                   ),// output [7:0]
             .force_ck_dly_en           (1'b0               ),// input
             .force_ck_dly_set_bin      (8'h05              ),// input [7:0]
             .dll_step                  (                   ),// output [7:0]
             .dll_lock                  (                   ),// output
             .init_read_clk_ctrl        (2'b0               ),// input [1:0]
             .init_slip_step            (4'b0               ),// input [3:0]
             .force_read_clk_ctrl       (1'b0               ),// input
             .ddrphy_gate_update_en     (1'b0               ),// input
             .update_com_val_err_flag   (                   ),// output [3:0]
             .rd_fake_stop              (1'b0               ) // input
       );*/
wire clk_125Mhz ;

GTP_INBUFGDS #(
    .IOSTANDARD("DEFAULT"),
    .TERM_DIFF("ON")
) u_gtp (
    .O(clk_125Mhz), // OUTPUT  
    .I(clk_p), // INPUT  
    .IB(clk_n) // INPUT  
);
 ddr3_test u_ddr3_test_h(
             .ref_clk                   (clk_125Mhz            ),
             .resetn                    (rstn_out           ),// input
             .ddr_init_done             (ddr_init_done      ),// output

             .pll_lock                  (pll_lock           ),// output

             .core_clk                  (core_clk),                                  // output

             .phy_pll_lock              (phy_pll_lock),                          // output
             .gpll_lock                 (gpll_lock),                                // output
             .rst_gpll_lock             (rst_gpll_lock),                        // output
             .ddrphy_cpd_lock           (ddrphy_cpd_lock),                    // output
             //.ddr_init_done             (ddr_init_done),                        // output


             .axi_awaddr                (axi_awaddr         ),// input [27:0]
             .axi_awuser_ap             (1'b0               ),// input
             .axi_awuser_id             (axi_awuser_id      ),// input [3:0]
             .axi_awlen                 (axi_awlen          ),// input [3:0]
             .axi_awready               (axi_awready        ),// output
             .axi_awvalid               (axi_awvalid        ),// input
             .axi_wdata                 (axi_wdata          ),
             .axi_wstrb                 (axi_wstrb          ),// input [31:0]
             .axi_wready                (axi_wready         ),// output
             .axi_wusero_id             (                   ),// output [3:0]
             .axi_wusero_last           (axi_wusero_last    ),// output
             .axi_araddr                (axi_araddr         ),// input [27:0]
             .axi_aruser_ap             (1'b0               ),// input
             .axi_aruser_id             (axi_aruser_id      ),// input [3:0]
             .axi_arlen                 (axi_arlen          ),// input [3:0]
             .axi_arready               (axi_arready        ),// output
             .axi_arvalid               (axi_arvalid        ),// input
             .axi_rdata                 (axi_rdata          ),// output [255:0]
             .axi_rid                   (axi_rid            ),// output [3:0]
             .axi_rlast                 (axi_rlast          ),// output
             .axi_rvalid                (axi_rvalid         ),// output

             .apb_clk                   (1'b0               ),// input
             .apb_rst_n                 (1'b1               ),// input
             .apb_sel                   (1'b0               ),// input
             .apb_enable                (1'b0               ),// input
             .apb_addr                  (8'b0               ),// input [7:0]
             .apb_write                 (1'b0               ),// input
             .apb_ready                 (                   ), // output
             .apb_wdata                 (16'b0              ),// input [15:0]
             .apb_rdata                 (                   ),// output [15:0]
//             .apb_int                   (                   ),// output

             .mem_rst_n                 (mem_rst_n          ),// output
             .mem_ck                    (mem_ck             ),// output
             .mem_ck_n                  (mem_ck_n           ),// output
             .mem_cke                   (mem_cke            ),// output
             .mem_cs_n                  (mem_cs_n           ),// output
             .mem_ras_n                 (mem_ras_n          ),// output
             .mem_cas_n                 (mem_cas_n          ),// output
             .mem_we_n                  (mem_we_n           ),// output
             .mem_odt                   (mem_odt            ),// output
             .mem_a                     (mem_a              ),// output [14:0]
             .mem_ba                    (mem_ba             ),// output [2:0]
             .mem_dqs                   (mem_dqs            ),// inout [3:0]
             .mem_dqs_n                 (mem_dqs_n          ),// inout [3:0]
             .mem_dq                    (mem_dq             ),// inout [31:0]
             .mem_dm                    (mem_dm             ),// output [3:0]
             //debug

  .dbg_gate_start(1'b0),                      // input
  .dbg_cpd_start(1'b0),                        // input
  .dbg_ddrphy_rst_n(1'b1),                  // input
  .dbg_gpll_scan_rst(1'b0),                // input
  .samp_position_dyn_adj(1'b0),        // input
  .init_samp_position_even(32'd0),    // input [31:0]
  .init_samp_position_odd(32'd0),      // input [31:0]
  .wrcal_position_dyn_adj(1'b0),      // input
  .init_wrcal_position(32'd0),            // input [31:0]
  .force_read_clk_ctrl(1'b0),            // input
  .init_slip_step(16'd0),                      // input [15:0]
  .init_read_clk_ctrl(12'd0),              // input [11:0]
  .debug_calib_ctrl(),                  // output [33:0]
  .dbg_slice_status(),                  // output [67:0]
  .dbg_slice_state(),                    // output [87:0]
  .debug_data(),                              // output [275:0]
  .dbg_dll_upd_state(),                // output [1:0]
  .debug_gpll_dps_phase(),          // output [8:0]
  .dbg_rst_dps_state(),                // output [2:0]
  .dbg_tran_err_rst_cnt(),          // output [5:0]
  .dbg_ddrphy_init_fail(),          // output
  .debug_cpd_offset_adj(1'b0),          // input
  .debug_cpd_offset_dir(1'b0),          // input
  .debug_cpd_offset(10'd0),                  // input [9:0]
  .debug_dps_cnt_dir0(),              // output [9:0]
  .debug_dps_cnt_dir1(),              // output [9:0]
  .ck_dly_en(1'b0),                                // input
  .init_ck_dly_step(8'h0),                  // input [7:0]
  .ck_dly_set_bin(),                      // output [7:0]
  .align_error(),                            // output
  .debug_rst_state(),                    // output [3:0]
  .debug_cpd_state()                     // output [3:0]
       );
//心跳信号
     always@(posedge core_clk) begin
        if (!ddr_init_done)
            cnt <= 27'd0;
        else if ( cnt >= TH_1S )
            cnt <= 27'd0;
        else
            cnt <= cnt + 27'd1;
     end

     always @(posedge core_clk)
        begin
        if (!ddr_init_done)
            heart_beat_led <= 1'd1;
        else if ( cnt >= TH_1S )
            heart_beat_led <= ~heart_beat_led;
    end
                 
/////////////////////////////////////////////////////////////////////////////////////
endmodule

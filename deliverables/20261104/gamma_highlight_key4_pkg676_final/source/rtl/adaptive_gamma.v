`timescale 1ns/1ps
// Frame-latched adaptive gamma. Statistics use pre-enhancement valid source
// samples only, excluding out-of-image fill. Hysteresis prevents mode flicker.
// Mode 0=linear, 1=brighten gamma .60, 2=darken gamma 1.60,
// 3=localized highlight roll-off. Clipped sensor values cannot be recovered.
module adaptive_gamma(
    input wire clk,rst_n,frame_begin,frame_end,enable,
    input wire in_valid,in_inside,
    input wire [15:0] in_pixel,
    output reg out_valid,
    output reg [15:0] out_pixel,
    output reg [1:0] mode
);
    `include "source/rtl/gamma_tables.vh"
    `include "source/rtl/video_contract.vh"
    // One frame is at most 1920x1080 samples; RGB565 luminance tops out at 250.
    localparam integer FRAME_SAMPLE_MAX=`VC_WIDTH*`VC_HEIGHT;
    localparam integer SAMPLE_COUNT_WIDTH=$clog2(FRAME_SAMPLE_MAX+1);
    localparam integer LUMINANCE_SUM_WIDTH=$clog2(FRAME_SAMPLE_MAX*250+1);
    reg [1:0] next_mode;
    reg [LUMINANCE_SUM_WIDTH-1:0] luminance_sum;
    reg [SAMPLE_COUNT_WIDTH-1:0] sample_count;
    reg [SAMPLE_COUNT_WIDTH-1:0] highlight_count;
    wire [9:0] lum_sum={2'd0,in_pixel[15:11],3'd0}+
                      {1'd0,in_pixel[10:5],3'd0}+{2'd0,in_pixel[4:0],3'd0};
    wire [7:0] luminance=lum_sum[9:2];
    wire [LUMINANCE_SUM_WIDTH-1:0] low70=sample_count*70;
    wire [LUMINANCE_SUM_WIDTH-1:0] low90=sample_count*90;
    wire [LUMINANCE_SUM_WIDTH-1:0] high170=sample_count*170;
    wire [LUMINANCE_SUM_WIDTH-1:0] high190=sample_count*190;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            mode<=0;next_mode<=0;luminance_sum<=0;sample_count<=0;highlight_count<=0;out_valid<=0;
        end else begin
            out_valid<=in_valid;
            if(frame_begin) begin
                mode<=enable?next_mode:2'd0;luminance_sum<=0;sample_count<=0;highlight_count<=0;
            end else if(in_valid && in_inside) begin
                luminance_sum<=luminance_sum+luminance;sample_count<=sample_count+1'b1;
                if(luminance>=8'd220) highlight_count<=highlight_count+1'b1;
            end
            if(frame_end) begin
                if(sample_count==0) next_mode<=0;
                else if(luminance_sum<low70 || (mode==1 && luminance_sum<low90)) next_mode<=1;
                else if(luminance_sum>high190 || (mode==2 && luminance_sum>high170)) next_mode<=2;
                else if(highlight_count>(sample_count>>4) ||
                        (mode==3 && highlight_count>(sample_count>>5))) next_mode<=3;
                else next_mode<=0;
            end
        end
    end
    always @(posedge clk) begin
        if(mode==1) out_pixel<={bright5(in_pixel[15:11]),bright6(in_pixel[10:5]),bright5(in_pixel[4:0])};
        else if(mode==2) out_pixel<={dark5(in_pixel[15:11]),dark6(in_pixel[10:5]),dark5(in_pixel[4:0])};
        else if(mode==3) out_pixel<={highlight5(in_pixel[15:11]),highlight6(in_pixel[10:5]),highlight5(in_pixel[4:0])};
        else out_pixel<=in_pixel;
    end
endmodule

`timescale 1ns/1ps
// Four-stage separable interpolation. Round once after vertical interpolation;
// no premature horizontal rounding. Fractions Q0.8; RGB565 channels independent.
module bilinear_rgb(
    input wire clk,rst_n,in_valid,in_inside,
    input wire [15:0] p00,p01,p10,p11,
    input wire [7:0] wx,wy,
    output reg out_valid,out_inside,
    output reg [15:0] pixel
);
    wire [8:0] ax=9'd256-{1'b0,wx},bx={1'b0,wx};
    reg [13:0] r00,r01,r10,r11,b00,b01,b10,b11;
    reg [14:0] g00,g01,g10,g11;
    reg [14:0] rh0,rh1,bh0,bh1;
    reg [15:0] gh0,gh1;
    reg [7:0] wy0,wy1;
    wire [8:0] ay=9'd256-{1'b0,wy1},by={1'b0,wy1};
    reg [23:0] rv0,rv1,bv0,bv1;
    reg [24:0] gv0,gv1;
    reg [2:0] vp,ip;
    wire [24:0] rout={1'b0,rv0}+{1'b0,rv1}+25'd32768;
    wire [25:0] gout={1'b0,gv0}+{1'b0,gv1}+26'd32768;
    wire [24:0] bout={1'b0,bv0}+{1'b0,bv1}+25'd32768;
    always @(posedge clk) begin
        r00<=p00[15:11]*ax;r01<=p01[15:11]*bx;r10<=p10[15:11]*ax;r11<=p11[15:11]*bx;
        g00<=p00[10:5]*ax;g01<=p01[10:5]*bx;g10<=p10[10:5]*ax;g11<=p11[10:5]*bx;
        b00<=p00[4:0]*ax;b01<=p01[4:0]*bx;b10<=p10[4:0]*ax;b11<=p11[4:0]*bx;
        wy0<=wy;wy1<=wy0;
        rh0<=r00+r01;rh1<=r10+r11;gh0<=g00+g01;gh1<=g10+g11;bh0<=b00+b01;bh1<=b10+b11;
        rv0<=rh0*ay;rv1<=rh1*by;gv0<=gh0*ay;gv1<=gh1*by;bv0<=bh0*ay;bv1<=bh1*by;
        pixel<=ip[2] ? {rout[20:16],gout[21:16],bout[20:16]} : 16'd0;
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin vp<=0;ip<=0;out_valid<=0;out_inside<=0;end
        else begin vp<={vp[1:0],in_valid};ip<={ip[1:0],in_inside};out_valid<=vp[2];out_inside<=ip[2];end
    end
endmodule

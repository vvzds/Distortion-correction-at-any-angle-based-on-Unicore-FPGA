`timescale 1ns/1ps
// Five-tap horizontal enhancement after the corrected DDR frame. Two pixels
// of latency are applied to RGB, DE, HS and VS together. No DDR traffic.
// level_core is synchronized and latched on VS: 0 is exact bypass; 1..3 scale
// a bounded luma-curvature correction. Black fill and strong edges are guarded.
module display_sharpen(
    input wire pix_clk,pix_rst_n,
    input wire [1:0] level_core,
    input wire [15:0] rgb_in,
    input wire de_in,hs_in,vs_in,
    output reg [15:0] rgb_out,
    output reg de_out,hs_out,vs_out
);
    reg [1:0] level_meta,level_sync,level_frame;
    reg vs_prev;
    reg [1:0] de_delay,hs_delay,vs_delay;
    reg [15:0] p1,p2,p3,p4;
    wire [15:0] filtered;

    // The UART setting is stable for many frames; only apply it on VS rise.
    always @(posedge pix_clk or negedge pix_rst_n) begin
        if(!pix_rst_n) begin
            level_meta<=0;level_sync<=0;level_frame<=0;
            vs_prev<=0;de_delay<=0;hs_delay<=0;vs_delay<=0;
            p1<=0;p2<=0;p3<=0;p4<=0;
            rgb_out<=0;de_out<=0;hs_out<=0;vs_out<=0;
        end else begin
            level_meta<=level_core;
            level_sync<=level_meta;
            if(vs_in && !vs_prev) level_frame<=level_sync;
            vs_prev<=vs_in;
            hs_delay<={hs_delay[0],hs_in};
            vs_delay<={vs_delay[0],vs_in};
            de_delay<={de_delay[0],de_in};
            if(de_in && !de_delay[0]) begin
                p1<=rgb_in;p2<=rgb_in;p3<=rgb_in;p4<=rgb_in;
            end else begin
                p4<=p3;p3<=p2;p2<=p1;
                p1<=de_in?rgb_in:p1;
            end
            rgb_out<=filtered;
            de_out<=de_delay[1];
            hs_out<=hs_delay[1];
            vs_out<=vs_delay[1];
        end
    end

    // Approximate luma in 6-bit RGB565 units. The range guard excludes flat
    // noise, hard edges and black invalid-map fill from enhancement.
    function [5:0] luma;
        input [15:0] p;
        reg [7:0] total;
        begin
            total={p[15:11],1'b0}+{1'b0,p[10:5],1'b0}+{p[4:0],1'b0};
            luma=total[7:2];
        end
    endfunction
    function [5:0] max5;
        input [5:0] a,b,c,d,e;
        reg [5:0] m;
        begin
            m=a>b?a:b;m=m>c?m:c;m=m>d?m:d;max5=m>e?m:e;
        end
    endfunction
    function [5:0] min5;
        input [5:0] a,b,c,d,e;
        reg [5:0] m;
        begin
            m=a<b?a:b;m=m<c?m:c;m=m<d?m:d;min5=m<e?m:e;
        end
    endfunction
    function [5:0] clamp6;
        input signed [8:0] value;
        begin
            if(value<0) clamp6=0;
            else if(value>63) clamp6=63;
            else clamp6=value[5:0];
        end
    endfunction
    function [4:0] clamp5;
        input signed [8:0] value;
        begin
            if(value<0) clamp5=0;
            else if(value>31) clamp5=31;
            else clamp5=value[4:0];
        end
    endfunction

    wire [15:0] right_pixel=de_in?rgb_in:p1;
    wire [5:0] yl2=luma(p4),yl1=luma(p3),yc=luma(p2),yr1=luma(p1),yr2=luma(right_pixel);
    wire [5:0] span=max5(yl2,yl1,yc,yr1,yr2)-min5(yl2,yl1,yc,yr1,yr2);
    wire signed [8:0] curvature=($signed({3'b000,yc})<<<2)
                                -$signed({3'b000,yl2})-$signed({3'b000,yl1})
                                -$signed({3'b000,yr1})-$signed({3'b000,yr2});
    wire [8:0] magnitude=curvature[8]?-curvature:curvature;
    wire [8:0] scaled=level_frame==2'd1 ? magnitude>>4 :
                      level_frame==2'd2 ? magnitude>>3 : magnitude>>2;
    wire [3:0] limited=scaled>6 ? 4'd6 : scaled[3:0];
    wire signed [8:0] correction=curvature[8] ? -$signed({5'd0,limited}) :
                                                  $signed({5'd0,limited});
    wire signed [8:0] half_correction=correction<0 ?
        -((-correction+1)>>>1) : (correction+1)>>>1;
    wire do_sharpen=level_frame!=0 && span>=3 && span<=26 &&
                    yl2!=0 && yl1!=0 && yc!=0 && yr1!=0 && yr2!=0 && limited!=0;
    wire signed [8:0] r_value=$signed({4'd0,p2[15:11]})+half_correction;
    wire signed [8:0] g_value=$signed({3'd0,p2[10:5]})+correction;
    wire signed [8:0] b_value=$signed({4'd0,p2[4:0]})+half_correction;
    assign filtered=do_sharpen ?
        {clamp5(r_value),clamp6(g_value),clamp5(b_value)} : p2;
endmodule

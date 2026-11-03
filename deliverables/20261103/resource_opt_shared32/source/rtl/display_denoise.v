`timescale 1ns/1ps
// Edge-aware five-tap horizontal denoiser for the corrected RGB565 display path.
// It removes isolated one-pixel impulses and gently suppresses small local noise.
// RGB, DE, HS and VS share a two-pixel latency; no frame memory or DDR port is used.
module display_denoise(
    input wire pix_clk,
    input wire pix_rst_n,
    input wire [1:0] level_core,
    input wire [15:0] rgb_in,
    input wire de_in, hs_in, vs_in,
    output reg [15:0] rgb_out,
    output reg de_out, hs_out, vs_out
);
    reg [1:0] level_meta, level_sync, level_frame;
    reg vs_prev;
    reg [1:0] de_delay, hs_delay, vs_delay;
    reg [15:0] p1, p2, p3, p4;

    // Return the middle value of five unsigned channel samples.
    function [5:0] median5;
        input [5:0] a,b,c,d,e;
        reg [5:0] s0,s1,s2,s3,s4,t;
        begin
            s0=a; s1=b; s2=c; s3=d; s4=e;
            if(s0>s1) begin t=s0;s0=s1;s1=t;end
            if(s1>s2) begin t=s1;s1=s2;s2=t;end
            if(s2>s3) begin t=s2;s2=s3;s3=t;end
            if(s3>s4) begin t=s3;s3=s4;s4=t;end
            if(s0>s1) begin t=s0;s0=s1;s1=t;end
            if(s1>s2) begin t=s1;s1=s2;s2=t;end
            if(s2>s3) begin t=s2;s2=s3;s3=t;end
            if(s0>s1) begin t=s0;s0=s1;s1=t;end
            if(s1>s2) begin t=s1;s1=s2;s2=t;end
            if(s0>s1) begin t=s0;s0=s1;s1=t;end
            median5=s2;
        end
    endfunction

    function [5:0] blend_channel;
        input [5:0] center, median;
        input [1:0] strength;
        reg [7:0] mixed;
        begin
            case(strength)
                2'd1: mixed=({2'b0,center}*8'd3 + {2'b0,median} + 8'd2) >> 2;
                2'd2: mixed=({2'b0,center} + {2'b0,median} + 8'd1) >> 1;
                default: mixed=median;
            endcase
            blend_channel=mixed[5:0];
        end
    endfunction

    function [5:0] absdiff;
        input [5:0] a,b;
        begin absdiff=(a>b)?(a-b):(b-a); end
    endfunction

    wire [5:0] r_med=median5({1'b0,p4[15:11]}, {1'b0,p3[15:11]},
                              {1'b0,p2[15:11]}, {1'b0,p1[15:11]},
                              {1'b0,(de_in?rgb_in[15:11]:p1[15:11])});
    wire [5:0] g_med=median5({p4[10:5]}, {p3[10:5]}, {p2[10:5]},
                              {p1[10:5]}, (de_in?rgb_in[10:5]:p1[10:5]));
    wire [5:0] b_med=median5({1'b0,p4[4:0]}, {1'b0,p3[4:0]},
                              {1'b0,p2[4:0]}, {1'b0,p1[4:0]},
                              {1'b0,(de_in?rgb_in[4:0]:p1[4:0])});
    wire [5:0] r_left={1'b0,p3[15:11]}, r_right={1'b0,p1[15:11]};
    wire [5:0] g_left=p3[10:5], g_right=p1[10:5];
    wire [5:0] b_left={1'b0,p3[4:0]}, b_right={1'b0,p1[4:0]};
    wire neighbors_agree=(absdiff(r_left,r_right)<=6'd2) &&
                         (absdiff(g_left,g_right)<=6'd3) &&
                         (absdiff(b_left,b_right)<=6'd2);
    wire center_is_noisy=(absdiff({1'b0,p2[15:11]},r_med)>=6'd1) ||
                         (absdiff(p2[10:5],g_med)>=6'd2) ||
                         (absdiff({1'b0,p2[4:0]},b_med)>=6'd1);
    wire apply_filter=(level_frame!=0) && neighbors_agree && center_is_noisy;
    wire [5:0] r_filtered=blend_channel({1'b0,p2[15:11]},r_med,level_frame);
    wire [5:0] g_filtered=blend_channel(p2[10:5],g_med,level_frame);
    wire [5:0] b_filtered=blend_channel({1'b0,p2[4:0]},b_med,level_frame);
    wire [15:0] filtered=apply_filter ?
        {r_filtered[4:0],g_filtered,b_filtered[4:0]} : p2;

    always @(posedge pix_clk or negedge pix_rst_n) begin
        if(!pix_rst_n) begin
            level_meta<=0; level_sync<=0; level_frame<=0; vs_prev<=0;
            de_delay<=0; hs_delay<=0; vs_delay<=0;
            p1<=0; p2<=0; p3<=0; p4<=0;
            rgb_out<=0; de_out<=0; hs_out<=0; vs_out<=0;
        end else begin
            level_meta<=level_core;
            level_sync<=level_meta;
            if(vs_in && !vs_prev) level_frame<=level_sync;
            vs_prev<=vs_in;
            de_delay<={de_delay[0],de_in};
            hs_delay<={hs_delay[0],hs_in};
            vs_delay<={vs_delay[0],vs_in};

            // Replicate the first active pixel through the history taps so a
            // blanking interval cannot contaminate the first output pixels.
            if(de_in && !de_delay[0]) begin
                p1<=rgb_in; p2<=rgb_in; p3<=rgb_in; p4<=rgb_in;
            end else begin
                p4<=p3; p3<=p2; p2<=p1;
                p1<=de_in ? rgb_in : p1;
            end
            rgb_out<=filtered;
            de_out<=de_delay[1]; hs_out<=hs_delay[1]; vs_out<=vs_delay[1];
        end
    end
endmodule

`timescale 1ns/1ps
// Two 256x256 RGB565 patches, four parity banks. Each bilinear footprint
// accesses at most one pixel in each bank, allowing one sample every clock.
// Native DDR fills sixteen adjacent pixels per beat. All RAM reads synchronous.
module patch_store(
    input wire clk,rst_n,
    input wire load_valid,load_buffer,
    input wire [7:0] load_y,
    input wire [3:0] load_word,
    input wire [255:0] load_data,
    input wire sample_valid,sample_buffer,
    input wire [7:0] x0,y0,x1,y1,
    output reg out_valid,
    output reg [15:0] p00,p01,p10,p11
);
    wire [7:0] xe=x0[0]?x1:x0, xo=x0[0]?x0:x1;
    wire [7:0] ye=y0[0]?y1:y0, yo=y0[0]?y0:y1;
    wire [11:0] ra00={sample_buffer,ye[7:1],xe[7:4]};
    wire [11:0] ra01={sample_buffer,ye[7:1],xo[7:4]};
    wire [11:0] ra10={sample_buffer,yo[7:1],xe[7:4]};
    wire [11:0] ra11={sample_buffer,yo[7:1],xo[7:4]};
    wire [11:0] wa={load_buffer,load_y[7:1],load_word};
    reg [127:0] even_data,odd_data;
    integer k;
    always @* for(k=0;k<8;k=k+1) begin
        even_data[k*16+:16]=load_data[k*32+:16];
        odd_data[k*16+:16]=load_data[k*32+16+:16];
    end
    reg [127:0] ram00[0:4095],ram01[0:4095],ram10[0:4095],ram11[0:4095];
    reg [127:0] q00,q01,q10,q11;
    reg [15:0] b00,b01,b10,b11;
    reg [2:0] xe_index,xo_index;
    reg [1:0] parity0,parity_x,parity_y,parity_xy;
    reg [1:0] select0,select_x,select_y,select_xy;
    reg [1:0] vp;
    always @(posedge clk) begin
        if(load_valid && !load_y[0]) begin ram00[wa]<=even_data;ram01[wa]<=odd_data;end
        if(load_valid &&  load_y[0]) begin ram10[wa]<=even_data;ram11[wa]<=odd_data;end
        if(sample_valid) begin
            q00<=ram00[ra00];q01<=ram01[ra01];q10<=ram10[ra10];q11<=ram11[ra11];
            xe_index<=xe[3:1];xo_index<=xo[3:1];
            parity0<={y0[0],x0[0]};parity_x<={y0[0],x1[0]};
            parity_y<={y1[0],x0[0]};parity_xy<={y1[0],x1[0]};
        end
        b00<=q00[xe_index*16+:16];b01<=q01[xo_index*16+:16];
        b10<=q10[xe_index*16+:16];b11<=q11[xo_index*16+:16];
        select0<=parity0;select_x<=parity_x;select_y<=parity_y;select_xy<=parity_xy;
        case(select0) 0:p00<=b00;1:p00<=b01;2:p00<=b10;3:p00<=b11;endcase
        case(select_x) 0:p01<=b00;1:p01<=b01;2:p01<=b10;3:p01<=b11;endcase
        case(select_y) 0:p10<=b00;1:p10<=b01;2:p10<=b10;3:p10<=b11;endcase
        case(select_xy) 0:p11<=b00;1:p11<=b01;2:p11<=b10;3:p11<=b11;endcase
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin vp<=0;out_valid<=0;end
        else begin vp<={vp[0],sample_valid};out_valid<=vp[1];end
    end
endmodule

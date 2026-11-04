`timescale 1ns/1ps
// Text-only HDMI overlay. Default calibration rows are available immediately
// after reset; host UART rows can replace them without changing the video path.
// Four OSD rows show only camera calibration terms. Row writes use a held-data
// clock-domain handshake; visibility changes apply at VS so a displayed frame
// never mixes two enable states.
module video_osd(
    input wire core_clk,core_rst_n,
    input wire row_valid,enable,
    input wire [2:0] row_index,
    input wire [383:0] row_data,
    input wire pix_clk,pix_rst_n,
    input wire [11:0] x,y,
    input wire de,vs,
    input wire [23:0] rgb_in,
    output reg [23:0] rgb_out
);
    reg [383:0] transfer_data;
    reg [2:0] transfer_index;
    reg req_toggle;
    reg [1:0] ack_sync;
    reg ack_toggle;
    reg [1:0] req_sync,enable_sync;
    reg [383:0] lines[0:3];
    reg visible,vs_d;
    integer reset_row;

    // The 384-bit payload is held until the pixel clock acknowledges it.
    always @(posedge core_clk or negedge core_rst_n) begin
        if(!core_rst_n) begin
            transfer_data<=0;transfer_index<=0;req_toggle<=0;ack_sync<=0;
        end else begin
            ack_sync<={ack_sync[0],ack_toggle};
            if(row_valid && req_toggle==ack_sync[1]) begin
                transfer_data<=row_data;
                transfer_index<=row_index;
                req_toggle<=~req_toggle;
            end
        end
    end
    always @(posedge pix_clk or negedge pix_rst_n) begin
        if(!pix_rst_n) begin
            req_sync<=0;enable_sync<=0;ack_toggle<=0;
            visible<=0;vs_d<=0;
            // These defaults match calibration/ov5640_1080p.json. KEY4 can
            // therefore show useful parameters before the host connects.
            lines[0]<=384'h2020202020202020202020202020202020202020202020353330342E373035313D594620343031372E373035313D5846;
            lines[1]<=384'h20202020202020202020202020202020202020202020202020373738362E3836353D594320313333352E3338383D5843;
            lines[2]<=384'h20202020202020202020202020202020202020202020203839363635312E302B3D324B203338343138332E302D3D314B;
            lines[3]<=384'h20202020202020202020202020202020202020202020203131313030302E302D3D3250203330333030302E302D3D3150;
        end else begin
            req_sync<={req_sync[0],req_toggle};
            enable_sync<={enable_sync[0],enable};
            vs_d<=vs;
            if(vs && !vs_d) visible<=enable_sync[1];
            if(req_sync[1]!=ack_toggle) begin
                if(transfer_index<4) lines[transfer_index]<=transfer_data;
                ack_toggle<=req_sync[1];
            end
        end
    end

    function [4:0] font_row;
        input [7:0] ch;
        input [2:0] r;
        reg [34:0] glyph;
        begin
            case(ch)
                8'h41:glyph={5'b01110,5'b10001,5'b10001,5'b11111,5'b10001,5'b10001,5'b10001}; // A
                8'h42:glyph={5'b11110,5'b10001,5'b10001,5'b11110,5'b10001,5'b10001,5'b11110};
                8'h43:glyph={5'b01111,5'b10000,5'b10000,5'b10000,5'b10000,5'b10000,5'b01111};
                8'h44:glyph={5'b11110,5'b10001,5'b10001,5'b10001,5'b10001,5'b10001,5'b11110};
                8'h45:glyph={5'b11111,5'b10000,5'b10000,5'b11110,5'b10000,5'b10000,5'b11111};
                8'h46:glyph={5'b11111,5'b10000,5'b10000,5'b11110,5'b10000,5'b10000,5'b10000};
                8'h47:glyph={5'b01111,5'b10000,5'b10000,5'b10111,5'b10001,5'b10001,5'b01111};
                8'h48:glyph={5'b10001,5'b10001,5'b10001,5'b11111,5'b10001,5'b10001,5'b10001};
                8'h49:glyph={5'b11111,5'b00100,5'b00100,5'b00100,5'b00100,5'b00100,5'b11111};
                8'h4a:glyph={5'b00111,5'b00010,5'b00010,5'b00010,5'b10010,5'b10010,5'b01100};
                8'h4b:glyph={5'b10001,5'b10010,5'b10100,5'b11000,5'b10100,5'b10010,5'b10001};
                8'h4c:glyph={5'b10000,5'b10000,5'b10000,5'b10000,5'b10000,5'b10000,5'b11111};
                8'h4d:glyph={5'b10001,5'b11011,5'b10101,5'b10101,5'b10001,5'b10001,5'b10001};
                8'h4e:glyph={5'b10001,5'b11001,5'b10101,5'b10011,5'b10001,5'b10001,5'b10001};
                8'h4f:glyph={5'b01110,5'b10001,5'b10001,5'b10001,5'b10001,5'b10001,5'b01110};
                8'h50:glyph={5'b11110,5'b10001,5'b10001,5'b11110,5'b10000,5'b10000,5'b10000};
                8'h51:glyph={5'b01110,5'b10001,5'b10001,5'b10001,5'b10101,5'b10010,5'b01101};
                8'h52:glyph={5'b11110,5'b10001,5'b10001,5'b11110,5'b10100,5'b10010,5'b10001};
                8'h53:glyph={5'b01111,5'b10000,5'b10000,5'b01110,5'b00001,5'b00001,5'b11110};
                8'h54:glyph={5'b11111,5'b00100,5'b00100,5'b00100,5'b00100,5'b00100,5'b00100};
                8'h55:glyph={5'b10001,5'b10001,5'b10001,5'b10001,5'b10001,5'b10001,5'b01110};
                8'h56:glyph={5'b10001,5'b10001,5'b10001,5'b10001,5'b10001,5'b01010,5'b00100};
                8'h57:glyph={5'b10001,5'b10001,5'b10001,5'b10101,5'b10101,5'b10101,5'b01010};
                8'h58:glyph={5'b10001,5'b10001,5'b01010,5'b00100,5'b01010,5'b10001,5'b10001};
                8'h59:glyph={5'b10001,5'b10001,5'b01010,5'b00100,5'b00100,5'b00100,5'b00100};
                8'h5a:glyph={5'b11111,5'b00001,5'b00010,5'b00100,5'b01000,5'b10000,5'b11111};
                8'h30:glyph={5'b01110,5'b10001,5'b10011,5'b10101,5'b11001,5'b10001,5'b01110};
                8'h31:glyph={5'b00100,5'b01100,5'b00100,5'b00100,5'b00100,5'b00100,5'b01110};
                8'h32:glyph={5'b01110,5'b10001,5'b00001,5'b00010,5'b00100,5'b01000,5'b11111};
                8'h33:glyph={5'b11110,5'b00001,5'b00001,5'b01110,5'b00001,5'b00001,5'b11110};
                8'h34:glyph={5'b00010,5'b00110,5'b01010,5'b10010,5'b11111,5'b00010,5'b00010};
                8'h35:glyph={5'b11111,5'b10000,5'b10000,5'b11110,5'b00001,5'b00001,5'b11110};
                8'h36:glyph={5'b01110,5'b10000,5'b10000,5'b11110,5'b10001,5'b10001,5'b01110};
                8'h37:glyph={5'b11111,5'b00001,5'b00010,5'b00100,5'b01000,5'b01000,5'b01000};
                8'h38:glyph={5'b01110,5'b10001,5'b10001,5'b01110,5'b10001,5'b10001,5'b01110};
                8'h39:glyph={5'b01110,5'b10001,5'b10001,5'b01111,5'b00001,5'b00001,5'b01110};
                8'h2d:glyph={5'b00000,5'b00000,5'b00000,5'b11111,5'b00000,5'b00000,5'b00000};
                8'h2b:glyph={5'b00000,5'b00100,5'b00100,5'b11111,5'b00100,5'b00100,5'b00000};
                8'h2e:glyph={5'b00000,5'b00000,5'b00000,5'b00000,5'b00000,5'b01100,5'b01100};
                8'h3a:glyph={5'b00000,5'b01100,5'b01100,5'b00000,5'b01100,5'b01100,5'b00000};
                8'h2f:glyph={5'b00001,5'b00001,5'b00010,5'b00100,5'b01000,5'b10000,5'b10000};
                8'h3d:glyph={5'b00000,5'b11111,5'b00000,5'b11111,5'b00000,5'b00000,5'b00000};
                8'h25:glyph={5'b11001,5'b11010,5'b00010,5'b00100,5'b01000,5'b01011,5'b10011};
                8'h3f:glyph={5'b01110,5'b10001,5'b00001,5'b00010,5'b00100,5'b00000,5'b00100};
                8'h28:glyph={5'b00010,5'b00100,5'b01000,5'b01000,5'b01000,5'b00100,5'b00010};
                8'h29:glyph={5'b01000,5'b00100,5'b00010,5'b00010,5'b00010,5'b00100,5'b01000};
                default:glyph=35'd0;
            endcase
            case(r)
                0:font_row=glyph[34:30];1:font_row=glyph[29:25];
                2:font_row=glyph[24:20];3:font_row=glyph[19:15];
                4:font_row=glyph[14:10];5:font_row=glyph[9:5];
                default:font_row=glyph[4:0];
            endcase
        end
    endfunction

    reg [1:0] text_line;
    reg [11:0] line_top;
    reg line_hit;
    reg [7:0] ch;
    reg [4:0] bitmap;
    reg [5:0] col;
    reg [2:0] glyph_x,glyph_y;
    always @* begin
        text_line=0;line_top=0;line_hit=0;
        if(y>=32 && y<48) begin text_line=0;line_top=32;line_hit=1;end
        else if(y>=56 && y<72) begin text_line=1;line_top=56;line_hit=1;end
        else if(y>=80 && y<96) begin text_line=2;line_top=80;line_hit=1;end
        else if(y>=104 && y<120) begin text_line=3;line_top=104;line_hit=1;end
        col=(x-12'd32)>>4;
        glyph_x=(x-12'd32)>>1;
        glyph_y=(y-line_top)>>1;
        ch=8'h20;
        case(text_line)
            0:ch=lines[0][col*8+:8];
            1:ch=lines[1][col*8+:8];
            2:ch=lines[2][col*8+:8];
            3:ch=lines[3][col*8+:8];
        endcase
        bitmap=font_row(ch,glyph_y);
        rgb_out=rgb_in;
        if(de && visible && x>=24 && x<808 && y>=24 && y<128) begin
            rgb_out=24'h11242c;
            if(x==24 || x==807 || y==24 || y==127) rgb_out=24'h44b5a9;
            if(line_hit && x>=32 && x<800 && glyph_x<5 && glyph_y<7 && bitmap[4-glyph_x]) begin
                if(text_line==0) rgb_out=24'h69e1d2;
                else rgb_out=24'hf1f5f3;
            end
        end
    end
endmodule

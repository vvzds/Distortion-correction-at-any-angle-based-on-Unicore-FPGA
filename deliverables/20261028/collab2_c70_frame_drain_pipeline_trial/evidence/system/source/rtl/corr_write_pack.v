`include "source/rtl/video_contract.vh"
`timescale 1ns/1ps
// C33：两个原生8拍包乒乓。收集下一包与发送当前包并行，端口/地址单位不变。
// 不给像素接口增加回压；rect_wr_if 仍承担规定服务边界内的弹性缓存。
module corr_write_pack #(
    parameter FRAME_WORDS=`VC_FRAME_WORDS,
    parameter SLOT_BITS=`VC_SLOT_WORD_BITS
)(
    input wire clk,rst_n,begin_frame,
    input wire [2:0] frame_slot,
    input wire corr_wr_req,
    input wire [23:0] corr_wr_addr,
    input wire [31:0] corr_wr_data,
    output wire corr_wr_gnt,
    input wire corr_wr_commit,
    output wire frame_idle,
    output reg publish,protocol_error,
    output wire [23:0] awaddr,
    output wire [3:0] awlen,
    output wire awvalid,
    input wire awready,
    output wire [255:0] wdata,
    input wire wpull,wlast
);
    reg [255:0] buffer0[0:7],buffer1[0:7];
    reg [1:0] ready;
    reg active,committed,fill_bank,send_bank,sent;
    reg [5:0] fill;
    reg [2:0] beat;
    reg [23:0] expected_addr,packet_addr;
    reg [20:0] accepted_words,returned_words;
    assign frame_idle=!active;
    assign corr_wr_gnt=rst_n && active && !committed && !ready[fill_bank] &&
        accepted_words<FRAME_WORDS && corr_wr_addr==expected_addr;
    assign awaddr=packet_addr;
    assign awlen=4'd7;
    assign awvalid=rst_n && ready[send_bank] && !sent;
    assign wdata=send_bank?buffer1[beat]:buffer0[beat];
    wire accept=corr_wr_req && corr_wr_gnt;
    always @(posedge clk)begin
        if(accept)begin
            if(fill_bank)buffer1[fill[5:3]][32*fill[2:0]+:32]<=corr_wr_data;
            else buffer0[fill[5:3]][32*fill[2:0]+:32]<=corr_wr_data;
        end
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            ready<=0;active<=0;committed<=0;fill_bank<=0;send_bank<=0;sent<=0;
            fill<=0;beat<=0;expected_addr<=0;packet_addr<=0;accepted_words<=0;
            returned_words<=0;publish<=0;protocol_error<=0;
        end else begin
            publish<=0;
            if(begin_frame && !active)begin
                ready<=0;active<=1;committed<=0;fill_bank<=0;send_bank<=0;sent<=0;
                fill<=0;beat<=0;expected_addr<=frame_slot<<SLOT_BITS;
                packet_addr<=frame_slot<<SLOT_BITS;accepted_words<=0;returned_words<=0;
            end
            if(accept)begin
                fill<=fill+1'b1;expected_addr<=expected_addr+1'b1;
                accepted_words<=accepted_words+1'b1;
                if(fill==63)begin ready[fill_bank]<=1;fill_bank<=!fill_bank;end
            end
            if(awvalid && awready)sent<=1;
            if(sent && wpull)begin
                beat<=beat+1'b1;
                if(wlast != (beat==7))protocol_error<=1;
            end
            if(sent && wlast)begin
                sent<=0;ready[send_bank]<=0;send_bank<=!send_bank;beat<=0;
                packet_addr<=packet_addr+24'd64;returned_words<=returned_words+21'd64;
            end
            if(active && corr_wr_commit)begin
                committed<=1;
                if(accepted_words+accept!=FRAME_WORDS)protocol_error<=1;
            end
            if(active && committed && ready==0 && fill==0 &&
                accepted_words==FRAME_WORDS && returned_words==FRAME_WORDS)begin
                publish<=1;active<=0;committed<=0;
            end
        end
    end
endmodule

// 自适应Gamma：完整帧亮度反馈、滞回选档、下一帧原子切换。
// 像素固定1拍延迟、每拍可接收1像素；不产生反压、不使用乘法器/IP。
module adaptive_gamma #(
    parameter integer WIDTH = 1920,
    parameter integer HEIGHT = 1080
)(
    input wire clk, rst_n,
    input wire i_enable,
    input wire i_pix_vld,
    input wire [15:0] i_pix,
    input wire i_sop, i_eop, i_sof, i_eof,
    output reg o_pix_vld,
    output reg [15:0] o_pix
);
    localparam integer PIXELS = WIDTH * HEIGHT;
    // 1080p最大累加528768000，小于2^29；阈值在展开时计算。
    localparam [28:0] T56=PIXELS*56, T72=PIXELS*72;
    localparam [28:0] T88=PIXELS*88, T104=PIXELS*104;
    localparam [28:0] T152=PIXELS*152, T168=PIXELS*168;
    localparam [28:0] T184=PIXELS*184, T200=PIXELS*200;
    reg [28:0] sum;
    reg [21:0] count;
    reg [10:0] xpos, ypos;
    reg frame_open, frame_bad, enabled;
    reg [2:0] curve, pending_curve;
    wire [7:0] red={i_pix[15:11],i_pix[15:13]};
    wire [7:0] green={i_pix[10:5],i_pix[10:9]};
    wire [7:0] blue={i_pix[4:0],i_pix[4:2]};
    // 近似亮度(R+2G+B)/4，四舍五入；总线显式扩宽防止溢出。
    wire [9:0] luminance_sum={2'b0,red}+{1'b0,green,1'b0}+{2'b0,blue}+10'd2;
    wire [7:0] luminance=luminance_sum[9:2];
    wire [28:0] sum_with_pixel=sum+{21'd0,luminance};
    wire marker_ok=(i_sop==(xpos==0)) && (i_eop==(xpos==WIDTH-1)) &&
                   (i_eof==(count==PIXELS-1));
    wire first_marker_ok=i_sop && (i_eop==(WIDTH==1)) &&
                         (i_eof==(PIXELS==1));
    wire [2:0] pixel_curve=i_sof ? pending_curve : curve;
    wire pixel_enabled=i_sof ? i_enable : enabled;
    wire [15:0] mapped;
    adaptive_gamma_curve u_curve(.i_curve(pixel_curve),.i_pix(i_pix),.o_pix(mapped));

    function [2:0] choose_curve;
        input [2:0] current;
        input [28:0] total;
        begin
            // 相邻档各8级滞回；每完整帧最多移动一档。
            case(current)
                0: choose_curve=(total>=T72) ? 1 : 0;
                1: choose_curve=(total<T56) ? 0 : ((total>=T104) ? 2 : 1);
                2: choose_curve=(total<T88) ? 1 : ((total>=T168) ? 3 : 2);
                3: choose_curve=(total<T152) ? 2 : ((total>=T200) ? 4 : 3);
                4: choose_curve=(total<T184) ? 3 : 4;
                default: choose_curve=2;
            endcase
        end
    endfunction

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            o_pix_vld<=0; o_pix<=0; sum<=0; count<=0;
            xpos<=0; ypos<=0; frame_open<=0; frame_bad<=0;
            enabled<=0; curve<=2; pending_curve<=2;
        end else begin
            o_pix_vld<=i_pix_vld;
            o_pix<=pixel_enabled ? mapped : i_pix;
            if(i_pix_vld) begin
                if(i_sof) begin
                    // SOF丢弃未完成统计，既有完整帧的pending曲线保留。
                    curve<=pending_curve; enabled<=i_enable;
                    sum<={21'd0,luminance}; count<=1;
                    xpos<=(WIDTH==1) ? 0 : 1;
                    ypos<=(WIDTH==1) ? 1 : 0;
                    frame_open<=!i_eof; frame_bad<=!first_marker_ok;
                    if(PIXELS==1 && first_marker_ok)
                        pending_curve<=choose_curve(pending_curve,{21'd0,luminance});
                end else if(frame_open) begin
                    if(count<PIXELS) begin
                        sum<=sum_with_pixel; count<=count+1'b1;
                        if(xpos==WIDTH-1) begin xpos<=0; ypos<=ypos+1'b1; end
                        else xpos<=xpos+1'b1;
                    end else frame_bad<=1;
                    if(!marker_ok) frame_bad<=1;
                    if(i_eof) begin
                        frame_open<=0;
                        if(!frame_bad && marker_ok && count==PIXELS-1 &&
                           ypos==HEIGHT-1 && xpos==WIDTH-1)
                            pending_curve<=choose_curve(curve,sum_with_pixel);
                    end
                end
            end
        end
    end
endmodule

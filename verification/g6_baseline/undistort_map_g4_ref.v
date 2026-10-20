// 帧首计算 Q0.36 焦距倒数；随后按输出屏幕坐标生成源屏幕坐标 Q16.16。
module undistort_map_g4_ref (
    input  wire clk,
    input  wire rst_n,
    input  wire i_frame_init,
    input  wire signed [31:0] i_fx,i_fy,i_cx,i_cy,
    input  wire signed [31:0] i_k1,i_k2,i_p1,i_p2,
    input  wire signed [31:0] i_aff_a11,i_aff_a12,i_aff_a21,i_aff_a22,
    input  wire signed [31:0] i_aff_tx,i_aff_ty,
    input  wire i_aff_en,
    output reg  o_init_done,
    input  wire i_valid,
    input  wire [10:0] i_u,i_v,
    output reg  o_valid,
    output reg  [26:0] o_sx_q16,o_sy_q16
);
    localparam [1:0] IDLE=0, DIV_X=1, DIV_Y=2, READY=3;
    reg [1:0] state;
    reg signed [31:0] fx,fy,cx,cy,k1,k2,p1,p2;
    reg signed [31:0] a11,a12,a21,a22,tx,ty;
    reg aff_en,identity;
    reg [35:0] inv_fx,inv_fy;
    reg [52:0] div_shift,quotient;
    reg [32:0] remainder;
    reg [31:0] divisor;
    reg [5:0] div_count;
    wire [32:0] candidate={remainder[31:0],div_shift[52]};
    wire subtract_en=(candidate >= {1'b0,divisor});
    wire [52:0] quotient_next={quotient[51:0],subtract_en};

    reg signed [47:0] xp0,yp0;
    // G3：主点减法独立寄存，避免宽进位链与归一化乘法同拍串接。
    reg signed [47:0] dx_norm,dy_norm;
    reg [10:0] u_norm,v_norm;
    reg signed [31:0] xn1,yn1;
    // G2：Q48完整乘积先寄存，下一拍求和后统一截断，保留低位进位。
    reg signed [63:0] xx_sq,yy_sq,xy_sq;
    reg signed [31:0] xn_sq,yn_sq;
    reg [10:0] u_sq,v_sq;
    reg signed [31:0] xn2,yn2,xn3,yn3,xn4,yn4;
    reg signed [47:0] r2_2,xx2,yy2,xy2;
    reg signed [47:0] r2_3,xx3,yy3,xy3;
    reg signed [47:0] r2_4,xx4,yy4,xy4;
    // 合法极值组合下 r4 可超过 2^23；保留更宽的 Q24 容器，避免钳位前符号翻转。
    reg signed [63:0] r4_3;
    // G1：乘积、预加与末级累加分别寄存，切断进位链串接乘法器的路径。
    reg signed [63:0] kr1_4,kr2_4,radial5;
    reg signed [49:0] tan_x4,tan_y4;
    reg signed [31:0] xn5,yn5;
    reg signed [71:0] tan_xy_x5,tan_xy_y5,tan_x5,tan_y5;
    reg signed [71:0] tan_xy_x6,tan_xy_y6,tan_x6,tan_y6;
    reg signed [71:0] xrad6,yrad6,xd7,yd7;
    reg signed [111:0] sx8,sy8;
    reg [10:0] u0,u1,u2,u3,u4,u5,u6,u7,u8;
    reg [10:0] v0,v1,v2,v3,v4,v5,v6,v7,v8;
    reg [10:0] valid_pipe;

    wire signed [63:0] aff_px=$signed(a11)*$signed({1'b0,i_u})+
                                 $signed(a12)*$signed({1'b0,i_v});
    wire signed [63:0] aff_py=$signed(a21)*$signed({1'b0,i_u})+
                                 $signed(a22)*$signed({1'b0,i_v});
    wire signed [63:0] xn_mul=$signed(dx_norm)*$signed({1'b0,inv_fx});
    wire signed [63:0] yn_mul=$signed(dy_norm)*$signed({1'b0,inv_fy});
    wire signed [63:0] xx_mul=$signed(xn1)*$signed(xn1);
    wire signed [63:0] yy_mul=$signed(yn1)*$signed(yn1);
    wire signed [63:0] xy_mul=$signed(xn1)*$signed(yn1);
    wire signed [95:0] r4_mul=$signed(r2_2)*$signed(r2_2);
    wire signed [95:0] kr1_mul=$signed(k1)*$signed(r2_3);
    wire signed [95:0] kr2_mul=$signed(k2)*$signed(r4_3);
    wire signed [95:0] xrad_mul=$signed(xn5)*$signed(radial5);
    wire signed [95:0] yrad_mul=$signed(yn5)*$signed(radial5);
    wire signed [95:0] p1xy_mul=$signed(p1)*$signed(xy4);
    wire signed [95:0] p2xy_mul=$signed(p2)*$signed(xy4);
    wire signed [95:0] p2xx_mul=$signed(p2)*$signed(tan_x4);
    wire signed [95:0] p1yy_mul=$signed(p1)*$signed(tan_y4);
    wire signed [111:0] sx_mul=$signed(fx)*$signed(xd7);
    wire signed [111:0] sy_mul=$signed(fy)*$signed(yd7);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; o_init_done<=0;
            fx<=0;fy<=0;cx<=0;cy<=0;k1<=0;k2<=0;p1<=0;p2<=0;
            a11<=0;a12<=0;a21<=0;a22<=0;tx<=0;ty<=0;
            aff_en<=0;identity<=0;
            inv_fx<=0;inv_fy<=0;div_shift<=0;quotient<=0;
            remainder<=0;divisor<=0;div_count<=0;
            xp0<=0;yp0<=0;xn1<=0;yn1<=0;
            dx_norm<=0;dy_norm<=0;u_norm<=0;v_norm<=0;
            xx_sq<=0;yy_sq<=0;xy_sq<=0;xn_sq<=0;yn_sq<=0;
            u_sq<=0;v_sq<=0;
            xn2<=0;yn2<=0;xn3<=0;yn3<=0;xn4<=0;yn4<=0;
            r2_2<=0;xx2<=0;yy2<=0;xy2<=0;
            r2_3<=0;xx3<=0;yy3<=0;xy3<=0;
            r2_4<=0;xx4<=0;yy4<=0;xy4<=0;r4_3<=0;
            kr1_4<=0;kr2_4<=0;radial5<=0;tan_x4<=0;tan_y4<=0;
            xn5<=0;yn5<=0;
            tan_xy_x5<=0;tan_xy_y5<=0;tan_x5<=0;tan_y5<=0;
            tan_xy_x6<=0;tan_xy_y6<=0;tan_x6<=0;tan_y6<=0;
            xrad6<=0;yrad6<=0;xd7<=0;yd7<=0;sx8<=0;sy8<=0;
            u0<=0;u1<=0;u2<=0;u3<=0;u4<=0;u5<=0;u6<=0;
            v0<=0;v1<=0;v2<=0;v3<=0;v4<=0;v5<=0;v6<=0;
            u7<=0;u8<=0;v7<=0;v8<=0;
            valid_pipe<=0;o_valid<=0;o_sx_q16<=0;o_sy_q16<=0;
        end else begin
            if (i_frame_init && (state==IDLE || state==READY)) begin
                fx<=i_fx;fy<=i_fy;cx<=i_cx;cy<=i_cy;
                k1<=i_k1;k2<=i_k2;p1<=i_p1;p2<=i_p2;
                a11<=i_aff_a11;a12<=i_aff_a12;
                a21<=i_aff_a21;a22<=i_aff_a22;
                tx<=i_aff_tx;ty<=i_aff_ty;aff_en<=i_aff_en;
                identity<=(i_k1==0 && i_k2==0 && i_p1==0 && i_p2==0 &&
                    (!i_aff_en || (i_aff_a11==32'sh00010000 &&
                    i_aff_a22==32'sh00010000 && i_aff_a12==0 &&
                    i_aff_a21==0 && i_aff_tx==0 && i_aff_ty==0)));
                o_init_done<=0;
                div_shift<=53'h10000000000000;
                quotient<=0;remainder<=0;
                divisor<=i_fx[31:0];div_count<=6'd52;state<=DIV_X;
            end else case(state)
                DIV_X,DIV_Y: begin
                    div_shift<={div_shift[51:0],1'b0};
                    quotient<=quotient_next;
                    remainder<=subtract_en ? candidate-{1'b0,divisor} : candidate;
                    if(div_count==0) begin
                        if(state==DIV_X) begin
                            inv_fx<=quotient_next[35:0];
                            div_shift<=53'h10000000000000;
                            quotient<=0;remainder<=0;
                            divisor<=fy[31:0];div_count<=6'd52;state<=DIV_Y;
                        end else begin
                            inv_fy<=quotient_next[35:0];
                            state<=READY;o_init_done<=1;
                        end
                    end else div_count<=div_count-1'b1;
                end
                default: ;
            endcase

            valid_pipe<={valid_pipe[9:0],i_valid && o_init_done};
            o_valid<=valid_pipe[10];
            if(i_valid && o_init_done) begin
                xp0<=aff_en ? aff_px+$signed(tx) : $signed({1'b0,i_u,16'd0});
                yp0<=aff_en ? aff_py+$signed(ty) : $signed({1'b0,i_v,16'd0});
                u0<=i_u;v0<=i_v;
            end
            dx_norm<=xp0-$signed(cx);dy_norm<=yp0-$signed(cy);
            u_norm<=u0;v_norm<=v0;
            xn1<=xn_mul>>>28; yn1<=yn_mul>>>28;
            u1<=u_norm;v1<=v_norm;
            xx_sq<=xx_mul;yy_sq<=yy_mul;xy_sq<=xy_mul;
            xn_sq<=xn1;yn_sq<=yn1;u_sq<=u1;v_sq<=v1;
            xn2<=xn_sq;yn2<=yn_sq;
            xx2<=xx_sq>>>24; yy2<=yy_sq>>>24;
            xy2<=xy_sq>>>24;
            r2_2<=(xx_sq+yy_sq)>>>24;
            u2<=u_sq;v2<=v_sq;
            xn3<=xn2;yn3<=yn2;
            r2_3<=r2_2;xx3<=xx2;yy3<=yy2;xy3<=xy2;
            r4_3<=r4_mul>>>24;
            u3<=u2;v3<=v2;
            xn4<=xn3;yn4<=yn3;
            r2_4<=r2_3;xx4<=xx3;yy4<=yy3;xy4<=xy3;
            kr1_4<=kr1_mul>>>16;
            kr2_4<=kr2_mul>>>16;
            // 50位有符号预加容器覆盖48位输入之和，常数移位不引入乘法。
            tan_x4<=$signed({{2{r2_3[47]}},r2_3})+
                     ($signed({{2{xx3[47]}},xx3})<<<1);
            tan_y4<=$signed({{2{r2_3[47]}},r2_3})+
                     ($signed({{2{yy3[47]}},yy3})<<<1);
            u4<=u3;v4<=v3;
            radial5<=64'sd16777216+kr1_4+kr2_4;
            xn5<=xn4;yn5<=yn4;
            tan_xy_x5<=(p1xy_mul>>>16)<<<1;
            tan_xy_y5<=(p2xy_mul>>>16)<<<1;
            tan_x5<=p2xx_mul>>>16;
            tan_y5<=p1yy_mul>>>16;
            u5<=u4;v5<=v4;
            xrad6<=xrad_mul>>>24;
            yrad6<=yrad_mul>>>24;
            tan_xy_x6<=tan_xy_x5;tan_xy_y6<=tan_xy_y5;
            tan_x6<=tan_x5;tan_y6<=tan_y5;
            u6<=u5;v6<=v5;
            xd7<=xrad6+tan_xy_x6+tan_x6;
            yd7<=yrad6+tan_y6+tan_xy_y6;
            u7<=u6;v7<=v6;
            sx8<=(sx_mul>>>24)+$signed(cx);
            sy8<=(sy_mul>>>24)+$signed(cy);
            u8<=u7;v8<=v7;
            if(valid_pipe[10]) begin
                if(identity) begin
                    o_sx_q16<={u8,16'd0};
                    o_sy_q16<={v8,16'd0};
                end else begin
                    if(sx8<0) o_sx_q16<=0;
                    else if(sx8>112'sd125763584) o_sx_q16<=27'd125763584;
                    else o_sx_q16<=sx8[26:0];
                    if(sy8<0) o_sy_q16<=0;
                    else if(sy8>112'sd70713344) o_sy_q16<=27'd70713344;
                    else o_sy_q16<=sy8[26:0];
                end
            end
        end
    end
endmodule

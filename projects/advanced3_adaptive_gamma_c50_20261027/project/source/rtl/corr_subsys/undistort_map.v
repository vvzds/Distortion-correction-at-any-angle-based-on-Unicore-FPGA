// 帧首计算 Q0.36 焦距倒数；随后按输出屏幕坐标生成源屏幕坐标 Q16.16。
module undistort_map (
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

    // C20: isolate core coordinate generation from affine multiplication.
    // Accept exactly the original valid/ready event, then delay all payloads one cycle.
    reg [10:0] u_entry,v_entry;
    reg entry_valid;
    reg signed [47:0] xp0,yp0;
    // G3：主点减法独立寄存，避免宽进位链与归一化乘法同拍串接。
    reg signed [47:0] dx_norm,dy_norm;
    reg [10:0] u_norm,v_norm;
    // G6：完整归一化乘积先寄存；阻断N30到后续平方APM输入的组合链。
    reg signed [63:0] xn_product_g6,yn_product_g6;
    reg [10:0] u_product_g6,v_product_g6;
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
    reg signed [63:0] kr1_4,radial5;
    wire signed [63:0] kr2_4;
    reg signed [49:0] tan_x4,tan_y4;
    reg signed [31:0] xn5,yn5;
    reg signed [71:0] tan_xy_x5,tan_xy_y5,tan_x5,tan_y5;
    reg signed [71:0] tan_xy_x6,tan_xy_y6,tan_x6,tan_y6;
    reg signed [71:0] xd7,yd7;
    wire signed [71:0] xrad6;
    wire signed [71:0] yrad6;
    // G7：完整输出乘积寄存，切开乘法尾树和主点加法；不增加截断。
    reg signed [111:0] sx_product_g7,sy_product_g7;
    reg [10:0] u_product_g7,v_product_g7;
    reg signed [111:0] sx8,sy8;
    reg [10:0] u0,u1,u2,u3,u4,u5,u6,u7,u8;
    reg [10:0] v0,v1,v2,v3,v4,v5,v6,v7,v8;
    reg [23:0] valid_pipe;

    wire signed [63:0] aff_px=$signed(a11)*$signed({1'b0,u_entry})+
                                 $signed(a12)*$signed({1'b0,v_entry});
    wire signed [63:0] aff_py=$signed(a21)*$signed({1'b0,u_entry})+
                                 $signed(a22)*$signed({1'b0,v_entry});
    wire signed [63:0] xn_mul=$signed(dx_norm)*$signed({1'b0,inv_fx});
    wire signed [63:0] yn_mul=$signed(dy_norm)*$signed({1'b0,inv_fy});
    wire signed [63:0] xx_mul=$signed(xn1)*$signed(xn1);
    wire signed [63:0] yy_mul=$signed(yn1)*$signed(yn1);
    wire signed [63:0] xy_mul=$signed(xn1)*$signed(yn1);
    // C27：平方拆为 16bit 部分积并寄存，阻断 APM 级联的长组合链。
    wire signed [95:0] r4_mul;
    c27_square48_pipe4 u_r4_pipe(clk,rst_n,r2_2,r4_mul);
    wire signed [95:0] kr1_mul=$signed(k1)*$signed(r2_3);
    wire signed [95:0] kr2_pipe_product;
    g7_mul32x64_pipe4 u_k2_pipe(clk,rst_n,k2,r4_3,kr2_pipe_product);
    wire signed [95:0] xrad_pipe_product;
    g7_mul32x64_pipe4 u_xrad_pipe(clk,rst_n,xn5,radial5,xrad_pipe_product);
    wire signed [95:0] yrad_pipe_product;
    assign kr2_4 = kr2_pipe_product[79:16];
    assign xrad6 = xrad_pipe_product[95:24];
    assign yrad6 = yrad_pipe_product[95:24];
    g7_mul32x64_pipe4 u_yrad_pipe(clk,rst_n,yn5,radial5,yrad_pipe_product);
    wire signed [95:0] p1xy_mul=$signed(p1)*$signed(xy4_d3);
    wire signed [95:0] p2xy_mul=$signed(p2)*$signed(xy4_d3);
    wire signed [95:0] p2xx_mul=$signed(p2)*$signed(tan_x4_d3);
    wire signed [95:0] p1yy_mul=$signed(p1)*$signed(tan_y4_d3);
    wire signed [111:0] sx_mul=$signed(fx)*$signed(xd7);
    wire signed [111:0] sy_mul=$signed(fy)*$signed(yd7);

    reg signed [63:0] kr1_4_d1;
    reg signed [63:0] kr1_4_d2;
    reg signed [63:0] kr1_4_d3;
    reg signed [31:0] xn4_d1;
    reg signed [31:0] xn4_d2;
    reg signed [31:0] xn4_d3;
    reg signed [31:0] yn4_d1;
    reg signed [31:0] yn4_d2;
    reg signed [31:0] yn4_d3;
    reg signed [47:0] xy4_d1;
    reg signed [47:0] xy4_d2;
    reg signed [47:0] xy4_d3;
    reg signed [49:0] tan_x4_d1;
    reg signed [49:0] tan_x4_d2;
    reg signed [49:0] tan_x4_d3;
    reg signed [49:0] tan_y4_d1;
    reg signed [49:0] tan_y4_d2;
    reg signed [49:0] tan_y4_d3;
    reg [10:0] u4_d1;
    reg [10:0] u4_d2;
    reg [10:0] u4_d3;
    reg [10:0] v4_d1;
    reg [10:0] v4_d2;
    reg [10:0] v4_d3;
    reg signed [71:0] tan_xy_x6_d1;
    reg signed [71:0] tan_xy_x6_d2;
    reg signed [71:0] tan_xy_x6_d3;
    reg signed [71:0] tan_xy_y6_d1;
    reg signed [71:0] tan_xy_y6_d2;
    reg signed [71:0] tan_xy_y6_d3;
    reg signed [71:0] tan_x6_d1;
    reg signed [71:0] tan_x6_d2;
    reg signed [71:0] tan_x6_d3;
    reg signed [71:0] tan_y6_d1;
    reg signed [71:0] tan_y6_d2;
    reg signed [71:0] tan_y6_d3;
    reg [10:0] u6_d1;
    reg [10:0] u6_d2;
    reg [10:0] u6_d3;
    reg [10:0] v6_d1;
    reg [10:0] v6_d2;
    reg [10:0] v6_d3;

    reg signed [47:0] r2_2_r4d1;
    reg signed [47:0] r2_2_r4d2;
    reg signed [47:0] r2_2_r4d3;
    reg signed [47:0] r2_2_r4d4;
    reg signed [47:0] xx2_r4d1;
    reg signed [47:0] xx2_r4d2;
    reg signed [47:0] xx2_r4d3;
    reg signed [47:0] xx2_r4d4;
    reg signed [47:0] yy2_r4d1;
    reg signed [47:0] yy2_r4d2;
    reg signed [47:0] yy2_r4d3;
    reg signed [47:0] yy2_r4d4;
    reg signed [47:0] xy2_r4d1;
    reg signed [47:0] xy2_r4d2;
    reg signed [47:0] xy2_r4d3;
    reg signed [47:0] xy2_r4d4;
    reg signed [31:0] xn2_r4d1;
    reg signed [31:0] xn2_r4d2;
    reg signed [31:0] xn2_r4d3;
    reg signed [31:0] xn2_r4d4;
    reg signed [31:0] yn2_r4d1;
    reg signed [31:0] yn2_r4d2;
    reg signed [31:0] yn2_r4d3;
    reg signed [31:0] yn2_r4d4;
    reg signed [10:0] u2_r4d1;
    reg signed [10:0] u2_r4d2;
    reg signed [10:0] u2_r4d3;
    reg signed [10:0] u2_r4d4;
    reg signed [10:0] v2_r4d1;
    reg signed [10:0] v2_r4d2;
    reg signed [10:0] v2_r4d3;
    reg signed [10:0] v2_r4d4;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r2_2_r4d1<=0;
            r2_2_r4d2<=0;
            r2_2_r4d3<=0;
            r2_2_r4d4<=0;
            xx2_r4d1<=0;
            xx2_r4d2<=0;
            xx2_r4d3<=0;
            xx2_r4d4<=0;
            yy2_r4d1<=0;
            yy2_r4d2<=0;
            yy2_r4d3<=0;
            yy2_r4d4<=0;
            xy2_r4d1<=0;
            xy2_r4d2<=0;
            xy2_r4d3<=0;
            xy2_r4d4<=0;
            xn2_r4d1<=0;
            xn2_r4d2<=0;
            xn2_r4d3<=0;
            xn2_r4d4<=0;
            yn2_r4d1<=0;
            yn2_r4d2<=0;
            yn2_r4d3<=0;
            yn2_r4d4<=0;
            u2_r4d1<=0;
            u2_r4d2<=0;
            u2_r4d3<=0;
            u2_r4d4<=0;
            v2_r4d1<=0;
            v2_r4d2<=0;
            v2_r4d3<=0;
            v2_r4d4<=0;
            kr1_4_d1<=0;
            kr1_4_d2<=0;
            kr1_4_d3<=0;
            xn4_d1<=0;
            xn4_d2<=0;
            xn4_d3<=0;
            yn4_d1<=0;
            yn4_d2<=0;
            yn4_d3<=0;
            xy4_d1<=0;
            xy4_d2<=0;
            xy4_d3<=0;
            tan_x4_d1<=0;
            tan_x4_d2<=0;
            tan_x4_d3<=0;
            tan_y4_d1<=0;
            tan_y4_d2<=0;
            tan_y4_d3<=0;
            u4_d1<=0;
            u4_d2<=0;
            u4_d3<=0;
            v4_d1<=0;
            v4_d2<=0;
            v4_d3<=0;
            tan_xy_x6_d1<=0;
            tan_xy_x6_d2<=0;
            tan_xy_x6_d3<=0;
            tan_xy_y6_d1<=0;
            tan_xy_y6_d2<=0;
            tan_xy_y6_d3<=0;
            tan_x6_d1<=0;
            tan_x6_d2<=0;
            tan_x6_d3<=0;
            tan_y6_d1<=0;
            tan_y6_d2<=0;
            tan_y6_d3<=0;
            u6_d1<=0;
            u6_d2<=0;
            u6_d3<=0;
            v6_d1<=0;
            v6_d2<=0;
            v6_d3<=0;
            state<=IDLE; o_init_done<=0;
            fx<=0;fy<=0;cx<=0;cy<=0;k1<=0;k2<=0;p1<=0;p2<=0;
            a11<=0;a12<=0;a21<=0;a22<=0;tx<=0;ty<=0;
            aff_en<=0;identity<=0;
            inv_fx<=0;inv_fy<=0;div_shift<=0;quotient<=0;
            remainder<=0;divisor<=0;div_count<=0;
            u_entry<=0;v_entry<=0;entry_valid<=0;
            xp0<=0;yp0<=0;xn1<=0;yn1<=0;
            dx_norm<=0;dy_norm<=0;u_norm<=0;v_norm<=0;
            xn_product_g6<=0;yn_product_g6<=0;u_product_g6<=0;v_product_g6<=0;
            xx_sq<=0;yy_sq<=0;xy_sq<=0;xn_sq<=0;yn_sq<=0;
            u_sq<=0;v_sq<=0;
            xn2<=0;yn2<=0;xn3<=0;yn3<=0;xn4<=0;yn4<=0;
            r2_2<=0;xx2<=0;yy2<=0;xy2<=0;
            r2_3<=0;xx3<=0;yy3<=0;xy3<=0;
            r2_4<=0;xx4<=0;yy4<=0;xy4<=0;r4_3<=0;
            kr1_4<=0;radial5<=0;tan_x4<=0;tan_y4<=0;
            xn5<=0;yn5<=0;
            tan_xy_x5<=0;tan_xy_y5<=0;tan_x5<=0;tan_y5<=0;
            tan_xy_x6<=0;tan_xy_y6<=0;tan_x6<=0;tan_y6<=0;
            xd7<=0;yd7<=0;sx8<=0;sy8<=0;
            u0<=0;u1<=0;u2<=0;u3<=0;u4<=0;u5<=0;u6<=0;
            v0<=0;v1<=0;v2<=0;v3<=0;v4<=0;v5<=0;v6<=0;
            u7<=0;u8<=0;v7<=0;v8<=0;
            sx_product_g7<=0;sy_product_g7<=0;
            u_product_g7<=0;v_product_g7<=0;
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

            r2_2_r4d1<=r2_2;
            r2_2_r4d2<=r2_2_r4d1;
            r2_2_r4d3<=r2_2_r4d2;
            r2_2_r4d4<=r2_2_r4d3;
            xx2_r4d1<=xx2;
            xx2_r4d2<=xx2_r4d1;
            xx2_r4d3<=xx2_r4d2;
            xx2_r4d4<=xx2_r4d3;
            yy2_r4d1<=yy2;
            yy2_r4d2<=yy2_r4d1;
            yy2_r4d3<=yy2_r4d2;
            yy2_r4d4<=yy2_r4d3;
            xy2_r4d1<=xy2;
            xy2_r4d2<=xy2_r4d1;
            xy2_r4d3<=xy2_r4d2;
            xy2_r4d4<=xy2_r4d3;
            xn2_r4d1<=xn2;
            xn2_r4d2<=xn2_r4d1;
            xn2_r4d3<=xn2_r4d2;
            xn2_r4d4<=xn2_r4d3;
            yn2_r4d1<=yn2;
            yn2_r4d2<=yn2_r4d1;
            yn2_r4d3<=yn2_r4d2;
            yn2_r4d4<=yn2_r4d3;
            u2_r4d1<=u2;
            u2_r4d2<=u2_r4d1;
            u2_r4d3<=u2_r4d2;
            u2_r4d4<=u2_r4d3;
            v2_r4d1<=v2;
            v2_r4d2<=v2_r4d1;
            v2_r4d3<=v2_r4d2;
            v2_r4d4<=v2_r4d3;
            kr1_4_d1<=kr1_4;
            kr1_4_d2<=kr1_4_d1;
            kr1_4_d3<=kr1_4_d2;
            xn4_d1<=xn4;
            xn4_d2<=xn4_d1;
            xn4_d3<=xn4_d2;
            yn4_d1<=yn4;
            yn4_d2<=yn4_d1;
            yn4_d3<=yn4_d2;
            xy4_d1<=xy4;
            xy4_d2<=xy4_d1;
            xy4_d3<=xy4_d2;
            tan_x4_d1<=tan_x4;
            tan_x4_d2<=tan_x4_d1;
            tan_x4_d3<=tan_x4_d2;
            tan_y4_d1<=tan_y4;
            tan_y4_d2<=tan_y4_d1;
            tan_y4_d3<=tan_y4_d2;
            u4_d1<=u4;
            u4_d2<=u4_d1;
            u4_d3<=u4_d2;
            v4_d1<=v4;
            v4_d2<=v4_d1;
            v4_d3<=v4_d2;
            tan_xy_x6_d1<=tan_xy_x6;
            tan_xy_x6_d2<=tan_xy_x6_d1;
            tan_xy_x6_d3<=tan_xy_x6_d2;
            tan_xy_y6_d1<=tan_xy_y6;
            tan_xy_y6_d2<=tan_xy_y6_d1;
            tan_xy_y6_d3<=tan_xy_y6_d2;
            tan_x6_d1<=tan_x6;
            tan_x6_d2<=tan_x6_d1;
            tan_x6_d3<=tan_x6_d2;
            tan_y6_d1<=tan_y6;
            tan_y6_d2<=tan_y6_d1;
            tan_y6_d3<=tan_y6_d2;
            u6_d1<=u6;
            u6_d2<=u6_d1;
            u6_d3<=u6_d2;
            v6_d1<=v6;
            v6_d2<=v6_d1;
            v6_d3<=v6_d2;
            valid_pipe<={valid_pipe[22:0],i_valid && o_init_done};
            o_valid<=valid_pipe[23];
            entry_valid<=i_valid && o_init_done;
            if(i_valid && o_init_done) begin
                u_entry<=i_u;v_entry<=i_v;
            end
            if(entry_valid) begin
                xp0<=aff_en ? aff_px+$signed(tx) : $signed({1'b0,u_entry,16'd0});
                yp0<=aff_en ? aff_py+$signed(ty) : $signed({1'b0,v_entry,16'd0});
                u0<=u_entry;v0<=v_entry;
            end
            dx_norm<=xp0-$signed(cx);dy_norm<=yp0-$signed(cy);
            u_norm<=u0;v_norm<=v0;
            xn_product_g6<=xn_mul;yn_product_g6<=yn_mul;
            u_product_g6<=u_norm;v_product_g6<=v_norm;
            // 64位模积和右移/32位截断与G4一致，仅增加一拍。
            xn1<=xn_product_g6>>>28; yn1<=yn_product_g6>>>28;
            u1<=u_product_g6;v1<=v_product_g6;
            xx_sq<=xx_mul;yy_sq<=yy_mul;xy_sq<=xy_mul;
            xn_sq<=xn1;yn_sq<=yn1;u_sq<=u1;v_sq<=v1;
            xn2<=xn_sq;yn2<=yn_sq;
            xx2<=xx_sq>>>24; yy2<=yy_sq>>>24;
            xy2<=xy_sq>>>24;
            r2_2<=(xx_sq+yy_sq)>>>24;
            u2<=u_sq;v2<=v_sq;
            xn3<=xn2_r4d4;yn3<=yn2_r4d4;
            r2_3<=r2_2_r4d4;xx3<=xx2_r4d4;yy3<=yy2_r4d4;xy3<=xy2_r4d4;
            r4_3<=r4_mul>>>24;
            u3<=u2_r4d4;v3<=v2_r4d4;
            xn4<=xn3;yn4<=yn3;
            r2_4<=r2_3;xx4<=xx3;yy4<=yy3;xy4<=xy3;
            kr1_4<=kr1_mul>>>16;
            // 50位有符号预加容器覆盖48位输入之和，常数移位不引入乘法。
            tan_x4<=$signed({{2{r2_3[47]}},r2_3})+
                     ($signed({{2{xx3[47]}},xx3})<<<1);
            tan_y4<=$signed({{2{r2_3[47]}},r2_3})+
                     ($signed({{2{yy3[47]}},yy3})<<<1);
            u4<=u3;v4<=v3;
            radial5<=64'sd16777216+kr1_4_d3+kr2_4;
            xn5<=xn4_d3;yn5<=yn4_d3;
            tan_xy_x5<=(p1xy_mul>>>16)<<<1;
            tan_xy_y5<=(p2xy_mul>>>16)<<<1;
            tan_x5<=p2xx_mul>>>16;
            tan_y5<=p1yy_mul>>>16;
            u5<=u4_d3;v5<=v4_d3;
            tan_xy_x6<=tan_xy_x5;tan_xy_y6<=tan_xy_y5;
            tan_x6<=tan_x5;tan_y6<=tan_y5;
            u6<=u5;v6<=v5;
            xd7<=xrad6+tan_xy_x6_d3+tan_x6_d3;
            yd7<=yrad6+tan_y6_d3+tan_xy_y6_d3;
            u7<=u6_d3;v7<=v6_d3;
            sx_product_g7<=sx_mul;sy_product_g7<=sy_mul;
            u_product_g7<=u7;v_product_g7<=v7;
            sx8<=(sx_product_g7>>>24)+$signed(cx);
            sy8<=(sy_product_g7>>>24)+$signed(cy);
            u8<=u_product_g7;v8<=v_product_g7;
            if(valid_pipe[23]) begin
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

// Four registered stages; exact signed96 product, II=1. No early truncation.
module g7_mul32x64_pipe4(input wire clk,rst_n, input wire signed [31:0] a,
    input wire signed [63:0] b, output reg signed [95:0] product);
    reg signed [33:0] p00;
    reg signed [33:0] p01;
    reg signed [33:0] p02;
    reg signed [33:0] p03;
    reg signed [33:0] p10;
    reg signed [33:0] p11;
    reg signed [33:0] p12;
    reg signed [33:0] p13;
    reg signed [49:0] s00;
    reg signed [49:0] s01;
    reg signed [49:0] s10;
    reg signed [49:0] s11;
    reg signed [81:0] t0,t1;
    wire signed [98:0] total = $signed({{17{t0[81]}},t0}) + ($signed({{17{t1[81]}},t1}) <<< 16);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            p00<=0;
            p01<=0;
            p02<=0;
            p03<=0;
            p10<=0;
            p11<=0;
            p12<=0;
            p13<=0;
            s00<=0;
            s01<=0;
            s10<=0;
            s11<=0;
            t0<=0;t1<=0;product<=0;
        end else begin
            p00<=$signed({1'b0,a[15:0]})*$signed({1'b0,b[15:0]});
            p01<=$signed({1'b0,a[15:0]})*$signed({1'b0,b[31:16]});
            p02<=$signed({1'b0,a[15:0]})*$signed({1'b0,b[47:32]});
            p03<=$signed({1'b0,a[15:0]})*$signed({b[63],b[63:48]});
            p10<=$signed({a[31],a[31:16]})*$signed({1'b0,b[15:0]});
            p11<=$signed({a[31],a[31:16]})*$signed({1'b0,b[31:16]});
            p12<=$signed({a[31],a[31:16]})*$signed({1'b0,b[47:32]});
            p13<=$signed({a[31],a[31:16]})*$signed({b[63],b[63:48]});
            s00<=$signed({{16{p00[33]}},p00})+($signed({{16{p01[33]}},p01})<<<16);
            s01<=$signed({{16{p02[33]}},p02})+($signed({{16{p03[33]}},p03})<<<16);
            s10<=$signed({{16{p10[33]}},p10})+($signed({{16{p11[33]}},p11})<<<16);
            s11<=$signed({{16{p12[33]}},p12})+($signed({{16{p13[33]}},p13})<<<16);
            t0<=$signed({{32{s00[49]}},s00})+($signed({{32{s01[49]}},s01})<<<32);
            t1<=$signed({{32{s10[49]}},s10})+($signed({{32{s11[49]}},s11})<<<32);
            product<=total[95:0];
        end
    end
endmodule


// 有符号 48bit 平方，4 级流水，II=1；保留全部 96bit，无提前截断。
module c27_square48_pipe4(input wire clk,rst_n,
    input wire signed [47:0] a,output reg signed [95:0] product);
    reg signed [33:0] p00,p01,p02,p11,p12,p22;
    reg signed [35:0] c0,c1,c2,c3,c4;
    reg signed [52:0] lo,mid;
    reg signed [35:0] hi;
    wire signed [98:0] result=$signed({{46{lo[52]}},lo})+
        ($signed({{46{mid[52]}},mid})<<<32)+($signed({{63{hi[35]}},hi})<<<64);
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            p00<=0;p01<=0;p02<=0;p11<=0;p12<=0;p22<=0;
            c0<=0;c1<=0;c2<=0;c3<=0;c4<=0;lo<=0;mid<=0;hi<=0;product<=0;
        end else begin
            p00<=$signed({1'b0,a[15:0]})*$signed({1'b0,a[15:0]});
            p01<=$signed({1'b0,a[15:0]})*$signed({1'b0,a[31:16]});
            p02<=$signed({1'b0,a[15:0]})*$signed({a[47],a[47:32]});
            p11<=$signed({1'b0,a[31:16]})*$signed({1'b0,a[31:16]});
            p12<=$signed({1'b0,a[31:16]})*$signed({a[47],a[47:32]});
            p22<=$signed({a[47],a[47:32]})*$signed({a[47],a[47:32]});
            c0<=p00;c1<=$signed({{2{p01[33]}},p01})<<<1;
            c2<=$signed({{2{p11[33]}},p11})+($signed({{2{p02[33]}},p02})<<<1);
            c3<=$signed({{2{p12[33]}},p12})<<<1;c4<=p22;
            lo<=$signed({{17{c0[35]}},c0})+($signed({{17{c1[35]}},c1})<<<16);
            mid<=$signed({{17{c2[35]}},c2})+($signed({{17{c3[35]}},c3})<<<16);
            hi<=c4;product<=result[95:0];
        end
    end
endmodule

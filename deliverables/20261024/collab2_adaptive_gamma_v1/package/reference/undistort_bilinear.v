// RGB565 四邻域双线性插值，权重为 Q0.12。
module undistort_bilinear (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        i_valid,
    input  wire [15:0] i_p00,
    input  wire [15:0] i_p01,
    input  wire [15:0] i_p10,
    input  wire [15:0] i_p11,
    input  wire [11:0] i_wx,
    input  wire [11:0] i_wy,
    output reg         o_valid,
    output reg  [15:0] o_pixel
);
    reg [17:0] h0_r, h0_g, h0_b;
    reg [17:0] h1_r, h1_g, h1_b;
    reg [11:0] wy_d;
    reg        valid_d;

    wire [12:0] ax = 13'd4096 - {1'b0, i_wx};
    wire [12:0] bx = {1'b0, i_wx};
    wire [12:0] ay = 13'd4096 - {1'b0, wy_d};
    wire [12:0] by = {1'b0, wy_d};

    wire [30:0] sum_r = h0_r * ay + h1_r * by + 31'd8388608;
    wire [30:0] sum_g = h0_g * ay + h1_g * by + 31'd8388608;
    wire [30:0] sum_b = h0_b * ay + h1_b * by + 31'd8388608;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            h0_r <= 0; h0_g <= 0; h0_b <= 0;
            h1_r <= 0; h1_g <= 0; h1_b <= 0;
            wy_d <= 0; valid_d <= 0;
            o_valid <= 0; o_pixel <= 0;
        end else begin
            // 水平两点加权，结果保留 12 位小数。
            h0_r <= i_p00[15:11] * ax + i_p01[15:11] * bx;
            h0_g <= i_p00[10:5]  * ax + i_p01[10:5]  * bx;
            h0_b <= i_p00[4:0]   * ax + i_p01[4:0]   * bx;
            h1_r <= i_p10[15:11] * ax + i_p11[15:11] * bx;
            h1_g <= i_p10[10:5]  * ax + i_p11[10:5]  * bx;
            h1_b <= i_p10[4:0]   * ax + i_p11[4:0]   * bx;
            wy_d <= i_wy;
            valid_d <= i_valid;
            o_valid <= valid_d;
            if (valid_d)
                o_pixel <= {sum_r[28:24], sum_g[29:24], sum_b[28:24]};
        end
    end
endmodule

//============================================================================
// gamma_lut.v —— 三通道 Gamma LUT 像素映射模块（任务②，高阶3 本期范围）
//----------------------------------------------------------------------------
// 位置    : undistort_core 校正像素流 → rect_wr_if 之间（DDR 时钟域）
// 功能    : i_gamma_en=1 时按 3×256 点 LUT 对 RGB565 像素逐通道映射；
//           i_gamma_en=0 时像素原样旁路（bypass 对照演示）。
// 存储    : LUT 数据不存本模块，直接索引 param_mgr 输出的 6144bit 扁平总线
//           （避免双份 ~12k FF）；布局与 param_mgr_tb 已验证一致：
//           R=[2047:0]  G=[4095:2048]  B=[6143:4096]，每通道 256×8bit
// 格式    : RGB565 [15:11]R [10:5]G [4:0]B
//           索引扩位 5/6bit→8bit 采用高位复制 {c, c[MSB:MSB-2]}，
//           恒等 LUT 时经 8→5/6 截断可无损往返（数学性质，独立可验）
// 时序    : 严格 1 拍流水延迟，vld 透传；LUT/使能由 param_mgr 影子寄存器
//           在帧间隙原子切换，本模块逐拍采样无需额外同步
// 二期    : 直方图统计与 CDF 均衡不在本期（文档模块名 gamma_hist 预留扩展）
//============================================================================

module gamma_lut (
    input  wire          clk,
    input  wire          rst_n,
    // 校正像素流（DDR 域，来自双线性重采样）
    input  wire          i_pix_vld,
    input  wire  [15:0]  i_pix,           // RGB565
    output reg           o_pix_vld,
    output reg   [15:0]  o_pix,           // RGB565（映射或旁路）
    // Gamma 控制（来自 param_mgr，帧间隙原子切换）
    input  wire          i_gamma_en,
    input  wire  [6143:0] i_gamma_lut     // 3×256×8bit 扁平总线
);

    // 通道索引：5/6bit 高位复制扩位到 8bit（R/B 补 3 位，G 补 2 位）
    wire [7:0] r_idx = {i_pix[15:11], i_pix[15:13]};   // R5 → R8
    wire [7:0] g_idx = {i_pix[10:5],  i_pix[10:9]};    // G6 → G8
    wire [7:0] b_idx = {i_pix[4:0],   i_pix[4:2]};      // B5 → B8

    // 三通道查表（变量基址 + 常量位宽的选择，Verilog-2001 合法）
    wire [7:0] lut_r = i_gamma_lut[8*r_idx           +: 8];  // R 区 [2047:0]
    wire [7:0] lut_g = i_gamma_lut[2048 + 8*g_idx    +: 8];  // G 区 [4095:2048]
    wire [7:0] lut_b = i_gamma_lut[4096 + 8*b_idx    +: 8];  // B 区 [6143:4096]

    // 1 拍流水：bypass 直通 / 映射后取高 5/6 位重打包 RGB565
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            o_pix_vld <= 1'b0;
            o_pix     <= 16'h0;
        end else begin
            o_pix_vld <= i_pix_vld;
            o_pix     <= i_gamma_en ? {lut_r[7:3], lut_g[7:2], lut_b[7:3]}
                                    : i_pix;
        end
    end

endmodule

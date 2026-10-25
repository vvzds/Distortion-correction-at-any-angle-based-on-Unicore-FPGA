//============================================================================
// corr_top.v —— 校正子系统顶层（骨架版，V1.2 接口全冻结基线）
//----------------------------------------------------------------------------
// 功能：例化 param_mgr / undistort_core / gamma_lut / rect_wr_if 四模块并
//       完成逐名连线；实现帧节拍回接（自由连续处理）与 params_valid 使能
//       门控；拼装 32bit status 回读字。
// 依赖：undistort_core 与 rect_wr_if 的 RTL 由协作者交付；交付前使用
//       source/stub/ 下的同名 stub（module 名相同，替换文件即切换）。
// 端口：对外即 C1'-D2/C2'/D3/C3' 契约信号 + UART + 观测 pub_pulse，
//       经一号 correction_hook（生产模式 4）与链路直连，全程无寄存级。
// 状态字（status，i_status 冻结语义，V1.0 骨架冻结）：
//       [7:0]   fw_version  = 8'h12（V1.2 设计/协议版本）
//       [8]     params_valid（param_mgr.o_params_valid 直连）
//       [9]     frame_busy  （core.o_frame_busy 直连）
//       [15:10] 保留，读 0
//       [31:16] pub_count   校正帧发布脉冲计数（16bit 回绕）
// 时钟：单一 125 MHz ddr_clk 域（契约 D5-5.2），rst_n = ddr_init_done。
// 仿真：parameter CLK_FREQ 透传 param_mgr（TB 传 12.5MHz 实现 10 倍
//       波特加速，见 param_mgr_tb 同款手法），SIM_MODE 透传 core。
//============================================================================
`timescale 1ns/1ps

module corr_top #(
    parameter integer CLK_FREQ = 125_000_000,   // 时钟频率（透传 param_mgr）
    parameter         SIM_MODE = 0              // 透传 undistort_core（生产 0）
)(
    // ---- 时钟复位 ----
    input  wire        clk,
    input  wire        rst_n,
    // ---- UART ----
    input  wire        i_uart_rx,
    output wire        o_uart_tx,
    // ---- C1' 原始帧状态可见（链路 → 校正） ----
    input  wire [1:0]  i_frame_wcnt,
    input  wire        i_frame_update,
    // ---- C1'-D2 源帧保护 ----
    output wire        o_corr_src_hold_req,
    input  wire        i_corr_src_hold_gnt,
    input  wire [1:0]  i_corr_src_slot,
    output wire        o_corr_src_rel,
    // ---- C2' 行突发块读 ----
    output wire        o_corr_rd_req,
    output wire [23:0] o_corr_rd_addr,
    output wire [6:0]  o_corr_rd_len,
    input  wire        i_corr_rd_gnt,
    input  wire        i_corr_rd_vld,
    input  wire [255:0] i_corr_rd_data,
    input  wire        i_corr_rd_last,
    // ---- D3 目标槽申请 ----
    output wire        o_corr_wr_slot_req,
    input  wire        i_corr_wr_slot_gnt,
    input  wire [2:0]  i_corr_wr_slot,
    output wire        o_corr_wr_commit,
    // ---- C3' 整字写 ----
    output wire        o_corr_wr_req,
    output wire [23:0] o_corr_wr_addr,
    output wire [31:0] o_corr_wr_data,
    input  wire        i_corr_wr_gnt,
    // ---- 观测（链路发布脉冲，status 计数用，不参与控制） ----
    input  wire        i_corr_pub_pulse
);

    //==================================================================
    // 内部连线（§5.2(e) 逐名直连）
    //==================================================================
    wire signed [31:0] w_fx, w_fy, w_cx, w_cy, w_k1, w_k2, w_p1, w_p2;
    wire signed [31:0] w_a11, w_a12, w_a21, w_a22, w_tx, w_ty;
    wire        w_aff_en, w_params_valid, w_gamma_en;
    wire [6143:0] w_gamma_lut;
    wire        w_param_updated;
    wire        w_frame_busy;
    wire [31:0] w_stat_seg_loads,w_stat_line_loads,w_stat_line_hits;
    wire w_stat_line_stats_valid;
    wire        w_upd_pix_vld;
    wire [15:0] w_upd_pix;        // core → gamma_lut
    wire        w_core_sop, w_core_eop, w_core_sof, w_core_eof;
    wire        w_g_pix_vld;
    wire [15:0] w_g_pix;          // gamma_lut → rect_wr_if

    //==================================================================
    // 帧节拍回接 + params_valid 使能门控（自由连续处理）
    //------------------------------------------------------------------
    // 语义（§4.5）：顶层把"帧完成"接回 start 实现自由连续处理；
    //   start 仅在 params_valid=1 时发出；valid 拉低（越界组切换）
    //   后当前帧跑完即停，valid 恢复后自动重启。
    // 实现：armed 机制——valid=1 且 core 空闲且未发过 start → 发一次
    //   单脉冲并武装；core busy 起来后重新武装，等下一轮空闲。
    // 竞态消除（V1.0.1）：armed 在帧间隙第 1 拍读到的 valid 可能是
    //   swap 前旧值（param_mgr 的 swap_go = sh_dirty && !busy 为组合
    //   逻辑，busy 拉低当拍即申请切换、次拍生效），越界组切换时直接
    //   发 start 会让 core 采到切换后的越界参数组（原依赖 core 侧 D06
    //   兜底拒绝，真件行为不确定）。start 脉冲拍恰为 core 的参数采样
    //   拍（core 当拍看 start、次拍锁存参数组），故对 start 输出加当拍
    //   valid 组合门控：该拍 valid 已是 swap 后真值——越界组下 start
    //   被确定性抑制，零竞态窗口；合法组切换时序逐拍不变。
    //==================================================================
    reg        start_pulse;
    reg        armed;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            start_pulse <= 1'b0;
            armed       <= 1'b0;
        end else begin
            start_pulse <= 1'b0;              // 默认单周期脉冲
            if (!w_params_valid)
                armed <= 1'b0;                // 越界组：解除武装，停止启动
            else if (!w_frame_busy && !armed) begin
                start_pulse <= 1'b1;          // 空闲且合法：发起一帧
                armed       <= 1'b1;
            end else if (w_frame_busy)
                armed <= 1'b0;                // 帧已受理：重新武装等空闲
        end
    end

    // start 当拍 valid 门控（见上方"竞态消除"）：门控读到的 valid 与
    // core 将锁存的参数组严格同拍一致，越界组下 start 不出顶层。
    wire w_start_gated = start_pulse && w_params_valid;

    //==================================================================
    // 帧标志 1 拍对齐
    //------------------------------------------------------------------
    // 像素流经 gamma_lut 严格 1 拍流水（vld 透传、无标志透传端口），
    // core 的 sop/eop/sof/eof 必须同样打 1 拍，才能与 gamma 输出像素
    // 同拍到达 rect_wr_if（sof 拍 = 首像素 vld 拍，否则奇偶拼字错位）。
    //==================================================================
    reg r_sop, r_eop, r_sof, r_eof;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_sop <= 1'b0;  r_eop <= 1'b0;
            r_sof <= 1'b0;  r_eof <= 1'b0;
        end else begin
            r_sop <= w_core_sop;  r_eop <= w_core_eop;
            r_sof <= w_core_sof;  r_eof <= w_core_eof;
        end
    end

    //==================================================================
    // 校正帧发布计数（status [31:16]，16bit 回绕）
    //==================================================================
    reg [15:0] pub_count;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)             pub_count <= 16'd0;
        else if (i_corr_pub_pulse) pub_count <= pub_count + 16'd1;
    end

    //==================================================================
    // status 拼装（冻结语义见文件头）
    //==================================================================
    wire [31:0] w_status = {pub_count, 6'd0, w_frame_busy, w_params_valid, 8'h12};

    //==================================================================
    // param_mgr（UART 参数管理，我方已交付）
    //==================================================================
    param_mgr #(
        .CLK_FREQ (CLK_FREQ),
        .BAUD_RATE(115_200)
    ) u_param_mgr (
        .clk(clk), .rst_n(rst_n),
        .i_uart_rx(i_uart_rx), .o_uart_tx(o_uart_tx),
        .i_rect_busy(w_frame_busy), .o_param_updated(w_param_updated),
        .o_fx(w_fx), .o_fy(w_fy), .o_cx(w_cx), .o_cy(w_cy),
        .o_k1(w_k1), .o_k2(w_k2), .o_p1(w_p1), .o_p2(w_p2),
        .o_aff_a11(w_a11), .o_aff_a12(w_a12),
        .o_aff_a21(w_a21), .o_aff_a22(w_a22),
        .o_aff_tx(w_tx), .o_aff_ty(w_ty),
        .o_aff_en(w_aff_en), .o_params_valid(w_params_valid),
        .o_gamma_en(w_gamma_en), .o_gamma_lut(w_gamma_lut),
        .o_hist_rd_en(), .o_hist_ch(),          // 二期 stub，悬空
        .i_hist_count(24'd0),                   // 二期 stub
        .i_status(w_status)
    );

    //==================================================================
    // undistort_core（主引擎，二号协作者交付；交付前为同名 stub）
    //==================================================================
    undistort_core #(
        .SIM_MODE(SIM_MODE)
    ) u_core (
        .clk(clk), .rst_n(rst_n),
        .i_fx(w_fx), .i_fy(w_fy), .i_cx(w_cx), .i_cy(w_cy),
        .i_k1(w_k1), .i_k2(w_k2), .i_p1(w_p1), .i_p2(w_p2),
        .i_aff_a11(w_a11), .i_aff_a12(w_a12),
        .i_aff_a21(w_a21), .i_aff_a22(w_a22),
        .i_aff_tx(w_tx), .i_aff_ty(w_ty),
        .i_aff_en(w_aff_en),
        .i_frame_start(w_start_gated), .o_frame_busy(w_frame_busy),
        .o_corr_src_hold_req(o_corr_src_hold_req),
        .i_corr_src_hold_gnt(i_corr_src_hold_gnt),
        .i_corr_src_slot(i_corr_src_slot),
        .o_corr_src_rel(o_corr_src_rel),
        .o_corr_rd_addr(o_corr_rd_addr), .o_corr_rd_len(o_corr_rd_len),
        .o_corr_rd_req(o_corr_rd_req),
        .i_corr_rd_gnt(i_corr_rd_gnt), .i_corr_rd_vld(i_corr_rd_vld),
        .i_corr_rd_data(i_corr_rd_data), .i_corr_rd_last(i_corr_rd_last),
        .o_pix_vld(w_upd_pix_vld), .o_pix(w_upd_pix),
        .o_sop(w_core_sop), .o_eop(w_core_eop),
        .o_sof(w_core_sof), .o_eof(w_core_eof),
        .o_stat_frame_cnt(), .o_stat_line_loads(w_stat_line_loads),
        .o_stat_line_hits(w_stat_line_hits), .o_stat_pix_cnt(),
        .o_stat_seg_loads(w_stat_seg_loads),.o_stat_line_stats_valid(w_stat_line_stats_valid)
    );

    //==================================================================
    // gamma_lut（三通道 Gamma 映射，我方已交付，严格 1 拍流水）
    //==================================================================
    gamma_lut u_gamma (
        .clk(clk), .rst_n(rst_n),
        .i_pix_vld(w_upd_pix_vld), .i_pix(w_upd_pix),
        .o_pix_vld(w_g_pix_vld), .o_pix(w_g_pix),
        .i_gamma_en(w_gamma_en), .i_gamma_lut(w_gamma_lut)
    );

    //==================================================================
    // rect_wr_if（校正写回，协作者交付；交付前为同名 stub）
    //==================================================================
    rect_wr_if u_wr_if (
        .clk(clk), .rst_n(rst_n),
        .i_pix_vld(w_g_pix_vld), .i_pix(w_g_pix),
        // 标志打 1 拍对齐 gamma 像素（见上方"帧标志 1 拍对齐"注释）
        .i_sop(r_sop), .i_eop(r_eop),
        .i_sof(r_sof), .i_eof(r_eof),
        .o_corr_wr_slot_req(o_corr_wr_slot_req),
        .i_corr_wr_slot_gnt(i_corr_wr_slot_gnt),
        .i_corr_wr_slot(i_corr_wr_slot),
        .o_corr_wr_commit(o_corr_wr_commit),
        .o_corr_wr_req(o_corr_wr_req),
        .o_corr_wr_addr(o_corr_wr_addr),
        .o_corr_wr_data(o_corr_wr_data),
        .i_corr_wr_gnt(i_corr_wr_gnt)
    );

    // C1' 观测信号：当前设计不参与控制（帧事件由链路侧 D2 granter 语义
    // 消化），保留端口以对齐契约拓扑与后续扩展。

endmodule

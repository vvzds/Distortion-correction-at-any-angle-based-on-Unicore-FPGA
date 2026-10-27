//============================================================================
// param_mgr.v —— UART 参数管理模块（畸变校正子系统 · 任务①）
//----------------------------------------------------------------------------
// 功能：
//   1. UART(115200-8-N-1) 接收参数帧：帧头 0xAA 0x55 + cmd + len + payload + checksum
//      （checksum = payload 累加和低 8 位），坏帧（帧头错/校验错/长度错）直接丢弃；
//   2. 参数写入影子寄存器组，仅当 i_rect_busy==0（帧间隙）时原子切换到生效组，
//      并输出 o_param_updated 单周期脉冲；busy 期间参数滞留影子，不生效；
//   3. cmd 0x05 状态回读：经 o_uart_tx 回发 i_status（回发帧格式与下行同构）；
//   4. 直方图读接口 o_hist_rd_en/o_hist_ch/i_hist_count 本期做 stub（二期接 gamma_hist）；
//   5. o_params_valid 参数有效门控（D06 裁定，V1.2 新增）：复位默认 0；每次帧间隙
//      原子切换拍对影子组做 G02 范围校验（设计文档 §3.5 冻结表，畸变 8 + 仿射 6
//      全查、含端点），全部合法置 1、任一越界清 0——为"当前生效组是否合法"的
//      实时指示，供校正启动门控（core 侧另有兜底校验，D06 双保险）。
//
// 参数格式（全部 Q16.16 有符号定点，32 位，payload 小端字节序，直接拼位）：
//   cmd 0x01 len=32 : fx,fy,cx,cy,k1,k2,p1,p2（畸变 8 参数，基础任务2）
//   cmd 0x02 len=25 : a11,a12,a21,a22,tx,ty（仿射 6 参数，高阶1）；
//                     【V1.2 修订（G01）】第 25 字节（payload 下标 24）为专用使能
//                     字节：bit0=aff_en，bit7..1 保留写 0（读侧忽略）；原 V1.1
//                     "复用首字节 bit7 作使能"作废（该字节是 a11 最低字节，协议层互斥）
//   cmd 0x03         : Gamma 曲线（高阶3）。【协议修订 V1.1->V1.2】
//                     V1.1 原定 len=768 超出单字节长度上限 255，无法表达；
//                     修订为分 3 帧按通道下发：len=通道号(0=R,1=G,2=B)，
//                     payload 固定 256 字节（该通道 LUT）
//   cmd 0x04 len=4  : 模式位（小端 32 位字）：bit0=gamma_en，bit1=直方图均衡(二期)，其余保留
//   cmd 0x05 len=0  : 状态回读请求，FPGA 回发 0xAA 0x55 0x05 0x04 + status(4B 小端) + checksum
//
// 端口与 V1.1 设计文档 §7.2 对应关系（数组端口扁平化，Verilog-2001 兼容）：
//   文档 o_aff[0:5]  -> 本文件 o_aff_a11/a12/a21/a22/tx/ty（顺序一致：0=a11...5=ty）
//   文档 o_gamma_lut[0:767] -> 本文件 o_gamma_lut[6143:0] 扁平总线，
//                       字节 i = o_gamma_lut[8*i +: 8]，i=0..767，R/G/B 通道依次占 0-255/256-511/512-767
//
// 时钟域：单一 ddr_clk 域（CLK_FREQ 参数化，默认 125MHz，对应契约确认书 D5）。
// UART RX 输入经两级同步器（文档 §3.3 CDC 要求）。
//
// 仿真加速说明：TB 中传入缩小 10 倍的 CLK_FREQ（12.5MHz）实现千倍等效波特加速，
//              波特分频逻辑完全相同，仅时间轴缩放，不影响功能验证结论。
//============================================================================
`timescale 1ns/1ps

module param_mgr #(
    parameter integer CLK_FREQ = 125_000_000,   // 输入时钟频率(Hz)
    parameter integer BAUD_RATE = 115_200        // UART 波特率
)(
    input  wire        clk,                     // DDR 时钟域
    input  wire        rst_n,                   // 低有效异步复位
    input  wire        i_uart_rx,                // UART RX（115200-8-N-1，上位机/IMU 桥）
    output reg         o_uart_tx = 1'b1,        // UART TX（状态回读通道，空闲为高）
    // ---- 参数切换握手：仅在帧间隙生效，防撕裂 ----
    input  wire        i_rect_busy,              // 1=引擎帧处理中，0=帧间隙，可安全切换
    output reg         o_param_updated,          // 切换完成单周期脉冲
    // ---- 已生效参数组（Q16.16，源到 undistort_core）----
    output reg signed [31:0] o_fx,  o_fy,        // 焦距（像素单位）
    output reg signed [31:0] o_cx,  o_cy,        // 主点
    output reg signed [31:0] o_k1,  o_k2,        // 径向二阶系数
    output reg signed [31:0] o_p1,  o_p2,        // 切向系数
    output reg signed [31:0] o_aff_a11, o_aff_a12, o_aff_a21,  // 仿射矩阵（高阶1）
    output reg signed [31:0] o_aff_a22, o_aff_tx, o_aff_ty,
    output reg         o_aff_en,                 // 仿射使能（0x02 帧第 25 字节 bit0，V1.2 修订）
    output reg         o_params_valid,           // 参数组有效门控（D06：复位 0，切换拍按 G02 重算）
    output reg         o_gamma_en,               // Gamma 使能（0x04 帧模式字 bit0）
    output reg  [6143:0] o_gamma_lut,            // 768 字节 LUT 扁平总线：byte i = [8*i +: 8]
    // ---- 直方图统计读取（二期 gamma_hist 接入，本期 stub）----
    output wire        o_hist_rd_en,
    output wire [7:0]  o_hist_ch,
    input  wire [23:0] i_hist_count,
    // ---- 状态回读 ----
    input  wire [31:0] i_status                  // 回读内容：版本/帧计数（顶层提供）
);

    // 直方图接口 stub：端口保留，逻辑二期实现
    assign o_hist_rd_en = 1'b0;
    assign o_hist_ch    = 8'd0;
    // i_hist_count 本期不使用（综合器若告警未用信号可加 /* verilator lint_off */，仿真不受影响）

    //=========================================================
    // 1. UART RX：位采样（起始位中点确认 + 数据位中点采样）
    //=========================================================
    localparam integer DIV = CLK_FREQ / BAUD_RATE;   // 每 bit 的时钟周期数

    reg [1:0] rx_sync;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rx_sync <= 2'b11;
        else        rx_sync <= {rx_sync[0], i_uart_rx};   // 两级同步器（文档 §3.3）
    end
    wire rx = rx_sync[1];

    reg [15:0] rx_cnt;      // 位内分频计数
    reg [2:0]  rx_bit;      // 位计数（0-7）
    reg [1:0]  rx_st;       // 0=空闲, 1=数据位, 2=停止位
    reg [7:0]  rx_shift;
    reg        rx_byte_vld; // 字节接收完成单周期脉冲
    reg [7:0]  rx_byte;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rx_cnt <= 0; rx_bit <= 0; rx_st <= 0; rx_shift <= 0;
            rx_byte_vld <= 1'b0; rx_byte <= 8'h00;
        end else begin
            rx_byte_vld <= 1'b0;
            case (rx_st)
                2'd0: begin                     // 空闲：检测起始位（低）
                    if (rx == 1'b0) begin
                        if (rx_cnt == DIV/2 - 1) begin  // 起始位中点确认
                            rx_cnt <= 0; rx_bit <= 0; rx_st <= 2'd1;
                        end else rx_cnt <= rx_cnt + 1'b1;
                    end else rx_cnt <= 0;       // 空闲高电平，计数器归零
                end
                2'd1: begin                     // 8 个数据位，每位中点采样
                    if (rx_cnt == DIV - 1) begin
                        rx_cnt  <= 0;
                        rx_shift <= {rx, rx_shift[7:1]};   // LSB 先收
                        if (rx_bit == 3'd7) rx_st <= 2'd2;
                        else                rx_bit <= rx_bit + 1'b1;
                    end else rx_cnt <= rx_cnt + 1'b1;
                end
                2'd2: begin                     // 停止位
                    if (rx_cnt == DIV - 1) begin
                        rx_cnt <= 0; rx_st <= 0;
                        // 停止位应为高；不严格校验，字节交付
                        rx_byte      <= rx_shift;
                        rx_byte_vld <= 1'b1;
                    end else rx_cnt <= rx_cnt + 1'b1;
                end
                default: rx_st <= 0;
            endcase
        end
    end

    //=========================================================
    // 2. 帧协议解析状态机
    //    帧格式：AA 55 | cmd | len | payload(len B) | checksum
    //    坏帧（帧头/长度/校验和不符）整体丢弃，从下一字节重新找帧头
    //=========================================================
    localparam [2:0] P_IDLE = 3'd0,   // 等帧头 0xAA
                     P_HDR2 = 3'd1,   // 等帧头 0x55
                     P_CMD  = 3'd2,   // 命令字
                     P_LEN  = 3'd3,   // 长度/通道号
                     P_PAY  = 3'd4,   // payload
                     P_CHK  = 3'd5;   // 校验和

    reg [2:0] p_st;
    reg [7:0] p_cmd, p_len;
    reg [8:0] p_cnt;                 // payload 字节计数（0-255）
    reg [7:0] chk_acc;               // payload 累加和
    reg [7:0] pay_buf [0:255];       // payload 缓冲（最大 256B，0x03 单通道帧）
    reg [8:0] pay_target;            // 本帧应收 payload 字节数

    // 各 cmd 的合法 payload 长度（0x03 特殊：len=通道号，payload 固定 256B）
    // 返回 0 表示 cmd 非法
    function [8:0] exp_payload_len;
        input [7:0] c;
        begin
            case (c)
                8'h01:   exp_payload_len = 9'd32;
                8'h02:   exp_payload_len = 9'd25;   // V1.2（G01）：24B 系数 + 1B 尾使能
                8'h03:   exp_payload_len = 9'd256;   // gamma 单通道帧
                8'h04:   exp_payload_len = 9'd4;
                8'h05:   exp_payload_len = 9'd0;
                default: exp_payload_len = 9'd0;     // 非法 cmd，丢帧
            endcase
        end
    endfunction

    // 当前命令的期望 payload 长度（组合逻辑，供 P_LEN 拍比较）
    // 注：p_cmd 在 P_CMD 拍 nonblocking 更新，P_LEN 拍读到的已是本帧命令字
    wire [8:0] exp_len_cur = exp_payload_len(p_cmd);

    // 帧分发请求（解析完成且校验通过后单周期有效）
    reg        disp_valid;
    reg [7:0]  disp_cmd;
    reg [1:0]  disp_ch;             // 0x03 帧的通道号（来自 len 字节）

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            p_st <= P_IDLE; p_cmd <= 0; p_len <= 0; p_cnt <= 0;
            chk_acc <= 0; pay_target <= 0;
            disp_valid <= 1'b0; disp_cmd <= 8'h00; disp_ch <= 2'd0;
        end else begin
            disp_valid <= 1'b0;
            if (rx_byte_vld) begin
                case (p_st)
                    P_IDLE: if (rx_byte == 8'hAA) p_st <= P_HDR2;
                    P_HDR2: begin
                        if      (rx_byte == 8'h55) p_st <= P_CMD;   // 帧头命中
                        else if (rx_byte == 8'hAA) p_st <= P_HDR2;  // 连续 AA 保持
                        else                       p_st <= P_IDLE;  // 丢弃
                    end
                    P_CMD: begin
                        p_cmd <= rx_byte;
                        if (exp_payload_len(rx_byte) == 9'd0 &&
                            rx_byte != 8'h05)                    // 05 是唯一 len=0 合法命令
                            p_st <= P_IDLE;                      // 非法 cmd 丢帧
                        else
                            p_st <= P_LEN;
                    end
                    P_LEN: begin
                        p_len    <= rx_byte;
                        chk_acc  <= 8'h00;
                        p_cnt    <= 9'd0;
                        if (p_cmd == 8'h03) begin
                            // gamma 帧：len=通道号（0/1/2 合法），payload 固定 256B
                            if (rx_byte <= 8'd2) begin
                                pay_target <= 9'd256;
                                p_st <= P_PAY;
                            end else p_st <= P_IDLE;             // 通道号非法，丢帧
                        end else begin
                            // 其他帧：len 必须等于命令规定的长度
                            if (rx_byte == exp_len_cur[7:0]) begin
                                pay_target <= {1'b0, rx_byte};
                                p_st <= (rx_byte == 8'd0) ? P_CHK : P_PAY;
                            end else p_st <= P_IDLE;             // 长度不符，丢帧
                        end
                    end
                    P_PAY: begin
                        pay_buf[p_cnt[7:0]] <= rx_byte;
                        chk_acc <= chk_acc + rx_byte;
                        if (p_cnt == pay_target - 1'b1) p_st <= P_CHK;
                        else p_cnt <= p_cnt + 1'b1;
                    end
                    P_CHK: begin
                        if (rx_byte == chk_acc) begin             // 校验通过，请求分发
                            disp_valid <= 1'b1;
                            disp_cmd   <= p_cmd;
                            disp_ch    <= p_len[1:0];
                        end
                        // 校验失败：坏帧丢弃，不产生任何副作用
                        p_st <= P_IDLE;
                    end
                    default: p_st <= P_IDLE;
                endcase
            end
        end
    end

    //=========================================================
    // 3. 影子寄存器组（shadow）——命令分发写入
    //=========================================================
    reg signed [31:0] sh_fx, sh_fy, sh_cx, sh_cy, sh_k1, sh_k2, sh_p1, sh_p2;
    reg signed [31:0] sh_a11, sh_a12, sh_a21, sh_a22, sh_tx, sh_ty;
    reg               sh_aff_en, sh_gamma_en;
    reg [6143:0]      sh_gamma_lut;
    reg               sh_dirty;      // 影子有待切换的新参数

    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sh_fx<=0; sh_fy<=0; sh_cx<=0; sh_cy<=0; sh_k1<=0; sh_k2<=0; sh_p1<=0; sh_p2<=0;
            sh_a11<=0; sh_a12<=0; sh_a21<=0; sh_a22<=0; sh_tx<=0; sh_ty<=0;
            sh_aff_en<=1'b0; sh_gamma_en<=1'b0;
            sh_gamma_lut <= 6144'd0;
        end else if (disp_valid) begin
            case (disp_cmd)
                8'h01: begin   // 畸变 8 参数：32B 小端 Q16.16 依次拼位
                    sh_fx <= {pay_buf[3],  pay_buf[2],  pay_buf[1],  pay_buf[0]};
                    sh_fy <= {pay_buf[7],  pay_buf[6],  pay_buf[5],  pay_buf[4]};
                    sh_cx <= {pay_buf[11], pay_buf[10], pay_buf[9],  pay_buf[8]};
                    sh_cy <= {pay_buf[15], pay_buf[14], pay_buf[13], pay_buf[12]};
                    sh_k1 <= {pay_buf[19], pay_buf[18], pay_buf[17], pay_buf[16]};
                    sh_k2 <= {pay_buf[23], pay_buf[22], pay_buf[21], pay_buf[20]};
                    sh_p1 <= {pay_buf[27], pay_buf[26], pay_buf[25], pay_buf[24]};
                    sh_p2 <= {pay_buf[31], pay_buf[30], pay_buf[29], pay_buf[28]};
                end
                8'h02: begin   // 仿射 6 参数（24B 小端拼位，字节 0 bit7 原样归 a11，
                                // 不再兼任使能）+ 第 25 字节（下标 24）bit0 = 使能（G01 修订）
                    sh_a11    <= {pay_buf[3],  pay_buf[2],  pay_buf[1],  pay_buf[0]};
                    sh_aff_en <= pay_buf[24][0];
                    sh_a12 <= {pay_buf[7],  pay_buf[6],  pay_buf[5],  pay_buf[4]};
                    sh_a21 <= {pay_buf[11], pay_buf[10], pay_buf[9],  pay_buf[8]};
                    sh_a22 <= {pay_buf[15], pay_buf[14], pay_buf[13], pay_buf[12]};
                    sh_tx  <= {pay_buf[19], pay_buf[18], pay_buf[17], pay_buf[16]};
                    sh_ty  <= {pay_buf[23], pay_buf[22], pay_buf[21], pay_buf[20]};
                end
                8'h03: begin   // gamma 单通道 256B（协议修订：分 3 帧按通道下发）
                    case (disp_ch)
                        2'd0: for (i = 0; i < 256; i = i + 1) sh_gamma_lut[8*i     +: 8] <= pay_buf[i];
                        2'd1: for (i = 0; i < 256; i = i + 1) sh_gamma_lut[8*i+2048 +: 8] <= pay_buf[i];
                        2'd2: for (i = 0; i < 256; i = i + 1) sh_gamma_lut[8*i+4096 +: 8] <= pay_buf[i];
                        default: ;
                    endcase
                end
                8'h04: begin   // 模式位：bit0=gamma_en（bit1 直方图均衡二期）
                    sh_gamma_en <= pay_buf[0][0];
                end
                8'h05: ;      // 状态回读：不写影子，触发 TX
                default: ;
            endcase
        end
    end

    //=========================================================
    // 3.5 G02 参数范围校验（设计文档 §3.5 冻结表，含端点；Q16.16 有符号比较）
    //     fx,fy ∈ [128.0, 32767.99] → >= 0x0080_0000（上界 0x7FFF_FFFF 为
    //       signed 正数最大可表示值，天然覆盖，无需另查）
    //     cx ∈ [0,1919] / cy ∈ [0,1079]（屏幕坐标：非负 + 上界）
    //     k1,k2 ∈ ±0.5 / p1,p2 ∈ ±0.01 / a11..a22 ∈ ±2.0 / tx,ty ∈ ±4096.0（对称界）
    //=========================================================
    localparam signed [31:0] FX_MIN =  32'sh0080_0000,   // 128.0
                             CX_MAX =  32'sh077F_0000,   // 1919.0
                             CY_MAX =  32'sh0437_0000,   // 1079.0
                             K_LIM  =  32'sh0000_8000,   // 0.5
                             P_LIM  =  32'sh0000_028F,   // 0.01（≈655.36，含端点取 655）
                             A_LIM  =  32'sh0002_0000,   // 2.0
                             T_LIM  =  32'sh0100_0000;   // 4096.0

    // 对称界检查：-lim <= v <= lim
    function legal_sym;
        input signed [31:0] v;
        input signed [31:0] lim;
        begin
            legal_sym = (v >= -lim) && (v <= lim);
        end
    endfunction

    // 影子组 14 参数合法性（D06：切换拍判定，驱动 o_params_valid）
    wire sh_group_legal =
        (sh_fx >= FX_MIN) && (sh_fy >= FX_MIN) &&
        (sh_cx >= 32'sd0) && (sh_cx <= CX_MAX) &&
        (sh_cy >= 32'sd0) && (sh_cy <= CY_MAX) &&
        legal_sym(sh_k1, K_LIM) && legal_sym(sh_k2, K_LIM) &&
        legal_sym(sh_p1, P_LIM) && legal_sym(sh_p2, P_LIM) &&
        legal_sym(sh_a11, A_LIM) && legal_sym(sh_a12, A_LIM) &&
        legal_sym(sh_a21, A_LIM) && legal_sym(sh_a22, A_LIM) &&
        legal_sym(sh_tx, T_LIM) && legal_sym(sh_ty, T_LIM);

    //=========================================================
    // 4. 帧间隙原子切换：shadow -> 生效组（= 输出端口）
    //=========================================================
    wire swap_go = sh_dirty && !i_rect_busy;   // 帧间隙且影子有更新

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            o_fx<=0; o_fy<=0; o_cx<=0; o_cy<=0; o_k1<=0; o_k2<=0; o_p1<=0; o_p2<=0;
            o_aff_a11<=0; o_aff_a12<=0; o_aff_a21<=0; o_aff_a22<=0; o_aff_tx<=0; o_aff_ty<=0;
            o_aff_en<=1'b0; o_gamma_en<=1'b0;
            o_gamma_lut <= 6144'd0;
            o_param_updated <= 1'b0;
            o_params_valid <= 1'b0;               // D06：复位默认参数无效
        end else if (swap_go) begin
            o_fx<=sh_fx;   o_fy<=sh_fy;   o_cx<=sh_cx;   o_cy<=sh_cy;
            o_k1<=sh_k1;   o_k2<=sh_k2;   o_p1<=sh_p1;   o_p2<=sh_p2;
            o_aff_a11<=sh_a11; o_aff_a12<=sh_a12; o_aff_a21<=sh_a21; o_aff_a22<=sh_a22;
            o_aff_tx<=sh_tx;   o_aff_ty<=sh_ty;
            o_aff_en<=sh_aff_en; o_gamma_en<=sh_gamma_en;
            o_gamma_lut <= sh_gamma_lut;
            o_params_valid <= sh_group_legal;      // 切换拍按 G02 重算（越界组清 0，D06）
            o_param_updated <= 1'b1;
        end else begin
            o_param_updated <= 1'b0;
        end
    end

    // 影子 dirty 标志：新帧缓存置位（0x05 除外），切换完成清除
    // 注意优先级：同拍"新帧完成"与"切换执行"并存时，置位优先——先执行旧影子切换，
    // dirty 保持 1，下一帧间隙再切换新参数（语义正确）
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                    sh_dirty <= 1'b0;
        else if (disp_valid && disp_cmd != 8'h05) sh_dirty <= 1'b1;
        else if (swap_go)              sh_dirty <= 1'b0;
    end

    //=========================================================
    // 5. UART TX：cmd 0x05 状态回读（回发帧与下行同构）
    //    AA 55 05 04 status[7:0] status[15:8] status[23:16] status[31:24] chk
    //=========================================================
    reg [7:0] tx_bytes [0:8];
    reg       tx_run;
    reg [89:0] tx_shift;    // 9 字节 × 10bit（start + 8data + stop）展开
    reg [6:0]  tx_rem;      // 剩余 bit 数（90）
    reg [15:0] tx_cnt;
    reg       tx_gap;       // 起始位前停顿标志
    reg [15:0] tx_gap_cnt;  // 停顿计数
    localparam integer TX_GAP_CYC = 2 * DIV;   // 停顿 2 bit：下行帧 stop 位 + 1 空闲位

    wire tx_load = disp_valid && (disp_cmd == 8'h05);
    reg  tx_load_d;     // 打一拍：第一拍组装 tx_bytes，第二拍加载移位寄存器
    integer j;          // TX 块专用循环变量（与 shadow 块的 i 分离，避免共享冲突）

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) tx_load_d <= 1'b0;
        else        tx_load_d <= tx_load;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tx_run <= 1'b0; tx_shift <= 90'h0; tx_rem <= 7'd0; tx_cnt <= 16'd0;
            tx_gap <= 1'b0; tx_gap_cnt <= 16'd0;
            o_uart_tx <= 1'b1;
        end else begin
            if (tx_load) begin
                // 第一拍：组装回发帧 9 字节
                tx_bytes[0] <= 8'hAA;
                tx_bytes[1] <= 8'h55;
                tx_bytes[2] <= 8'h05;
                tx_bytes[3] <= 8'h04;
                tx_bytes[4] <= i_status[7:0];
                tx_bytes[5] <= i_status[15:8];
                tx_bytes[6] <= i_status[23:16];
                tx_bytes[7] <= i_status[31:24];
                tx_bytes[8] <= i_status[7:0] + i_status[15:8] + i_status[23:16] + i_status[31:24];
            end
            if (tx_load_d) begin
                // 第二拍：tx_bytes 已就绪，加载移位寄存器；先停顿 TX_GAP_CYC 拍再发起始位，
                // 保证回发帧不与下行帧最后停止位重叠（DUT 收完 checksum 即回发，上位机
                // 从发送切到接收监听需要时间，起始沿过早会被错过导致整帧错位）
                for (j = 0; j < 9; j = j + 1)
                    tx_shift[j*10 +: 10] <= {1'b1, tx_bytes[j], 1'b0};  // {stop,data,start}，LSB 先发
                tx_gap <= 1'b1;
                tx_gap_cnt <= 16'd0;
                tx_rem <= 7'd90;
                tx_cnt <= 16'd0;
            end else if (tx_gap) begin
                // 停顿期：o_uart_tx 保持空闲高，计满后输出起始位
                if (tx_gap_cnt == TX_GAP_CYC - 1) begin
                    tx_gap <= 1'b0;
                    tx_run <= 1'b1;
                    o_uart_tx <= 1'b0;   // 起始位现在才开始
                end else tx_gap_cnt <= tx_gap_cnt + 1'b1;
            end else if (tx_run) begin
                if (tx_cnt == DIV - 1) begin
                    tx_cnt   <= 16'd0;
                    tx_shift <= {1'b1, tx_shift[89:1]};   // 右移，高位补停止位电平
                    tx_rem   <= tx_rem - 1'b1;
                    o_uart_tx <= tx_shift[1];             // 下一 bit
                    if (tx_rem == 7'd1) begin
                        tx_run <= 1'b0;
                    end
                end else tx_cnt <= tx_cnt + 1'b1;
            end else begin
                o_uart_tx <= 1'b1;   // 空闲高
            end
        end
    end

endmodule

//============================================================================
// ideal_link.v —— 一号链路侧理想替身（仅仿真，TB 内例化）
//----------------------------------------------------------------------------
// 功能    : 模拟契约 C1'/D2/C2'/D3/C3' 的链路侧行为（DDR 仲裁/帧发布），
//           为 corr_top 顶层联调提供"链路环境"，不进综合。
// DDR 模型: reg [31:0] ddr_mem[0:2^23-1]（8 槽 x 2^20 字 = 32MiB），
//           TB 用层次引用直接填源帧数据（模拟一号采集写完成）。
// TB 配置  : ev_publish(单拍)+ev_slot：原始帧完成事件（锁最新帧/后到优先）；
//           wr_block_now(电平)：C3' 阻塞窗注入（TB 拉高 N 拍模拟行周期阻塞）。
// 契约实现:
//   C1'   : frame_wcnt=最新完成帧槽号(0-3)+frame_update 单拍脉冲；
//   D2    : hold_req 延迟 SRC_GNT_DLY 拍受理，gnt 锁 gnt 时刻最新完整帧
//           （后到优先），gnt 保持到 rel；
//   C2'   : rd_gnt 为 ready 电平(!in_flight)，req&&gnt 同拍受理、受理拍无
//           数据返回；延迟 RD_DLY 拍后连续 len+1 拍 vld（每拍 8 字，
//           word w=8p+j -> data[32j+31-:32]），last 对齐末拍；在途<=1；
//   D3    : slot_req 延迟 SLOT_GNT_DLY 拍 gnt（单拍），槽号 4-7 轮换分配
//           （无显示模型，排除项退化为轮换——四槽下永不等待语义保持）；
//   C3'   : wr_req 延迟 WR_GNT_DLY 拍建立 ready，req&&ready&&!block 拍收
//           一字写入 ddr_mem；commit 后 PUB_DLY 拍发 corr_pub_pulse。
//           发布链用独立 pub_active 标志而非断言[12]窗口 wr_committed：
//           下帧 slot gnt 拍 wr_committed 即被清除，而 commit 次拍 wr_if
//           就可发新帧 slot_req（D3 互锁出口）——若复用 wr_committed 做发布
//           门控，紧凑接续会把尚在倒计时的发布链一起掐断，pub 永不发出。
// 协议断言(violations 累加，TB 最终断言==0):
//   [1] C2' 受理拍 addr 未对齐行首(addr%960!=0)        [2] len!=119
//   [3] 受理拍未持源帧或地址域!=持有槽
//   [4] C2' req 未见 gnt 即撤回
//   [5] D2 rel 时仍有在途读(或 vld 未收完)              [6] rel 时未持有
//   [7] D3 slot_req 未受理即撤回
//   [8] C3' gnt 拍 addr 不连续(含首字非槽基址)          [9] addr 域!=gnt 槽
//   [10] commit 连续两拍(非单脉冲)
//   [11] commit 拍整帧未写满(期望槽基址+1,036,800 字)
//   [12] commit 后至下帧 slot gnt 前仍有 gnt 写
//============================================================================
`timescale 1ns/1ps

module ideal_link #(
    parameter integer RD_DLY      = 3,   // C2' 受理 -> 首 vld 延迟拍数
    parameter integer WR_GNT_DLY  = 1,   // C3' req -> ready 建立延迟
    parameter integer SRC_GNT_DLY = 2,   // D2  req -> gnt 延迟
    parameter integer SLOT_GNT_DLY= 2,  // D3  req -> gnt 延迟
    parameter integer PUB_DLY     = 5   // commit -> pub_pulse 延迟
)(
    input  wire        clk,
    input  wire        rst_n,
    // ---- TB 事件/配置 ----
    input  wire        ev_publish,        // 单拍：原始帧采集写完成
    input  wire [1:0]  ev_slot,           // 完成帧槽号(0-3)
    input  wire        wr_block_now,      // 电平：C3' 阻塞注入
    // ---- C1' 原始帧状态可见 ----
    output reg  [1:0]  frame_wcnt,
    output reg         frame_update,
    // ---- D2 源帧保护 ----
    input  wire        corr_src_hold_req,
    output reg         corr_src_hold_gnt,
    output reg  [1:0]  corr_src_slot,
    input  wire        corr_src_rel,
    // ---- C2' 行突发块读 ----
    input  wire        corr_rd_req,
    input  wire [23:0] corr_rd_addr,
    input  wire [6:0]  corr_rd_len,
    output wire        corr_rd_gnt,
    output wire        corr_rd_vld,
    output wire [255:0] corr_rd_data,
    output wire        corr_rd_last,
    // ---- D3 目标槽申请 ----
    input  wire        corr_wr_slot_req,
    output reg         corr_wr_slot_gnt,
    output reg  [2:0]  corr_wr_slot,
    input  wire        corr_wr_commit,
    // ---- C3' 整字写 ----
    input  wire        corr_wr_req,
    input  wire [23:0] corr_wr_addr,
    input  wire [31:0] corr_wr_data,
    output wire        corr_wr_gnt,
    // ---- 观测 ----
    output reg         corr_pub_pulse,
    output reg  [31:0] violations
);

    localparam [20:0] WORDS = 21'd1_036_800;   // 每帧字数

    //=========================================================
    // DDR 模型：8 槽 x 2^20 字（32 MiB），TB 层次引用填充
    //=========================================================
    reg [31:0] ddr_mem [0:(1<<23)-1];

    //=========================================================
    // C1'：最新完成帧 + 脉冲
    //=========================================================
    reg [1:0] latest_slot;

    //=========================================================
    // D2 granter
    //=========================================================
    reg [7:0] src_req_cnt;

    //=========================================================
    // C2' 读口
    //=========================================================
    reg        rd_in_flight;      // 受理未收完
    reg        rd_vld_active;     // vld 流激活
    reg [23:0] rd_addr_q;
    reg [6:0]  rd_len_q;
    reg [7:0]  rd_wait_cnt;
    reg [7:0]  rd_p_cnt;
    reg [31:0] rd_word_q [0:7];   // 预取快照（避免数组写事件重触发组合）
    reg        rd_req_d, slot_req_d, commit_d;

    //=========================================================
    // D3 granter + C3' 写口
    //=========================================================
    reg [2:0]  slot_assign;       // 轮换分配指针（4-7）
    reg [7:0]  slot_req_cnt;
    reg        slot_granted;     // 本轮 req 已受理标志
    reg [2:0]  wr_slot_q;        // 当前帧目标槽
    reg [23:0] wr_base_q;        // 当前帧槽基址
    reg [23:0] exp_wr_addr;      // 期望写地址（连续性断言）
    reg [7:0]  wr_req_cnt;
    reg        wr_ready;
    reg        wr_committed;      // commit 后至下帧 slot gnt 前的窗口（断言[12]）
    reg        pub_active;        // 发布倒计时激活（与 wr_committed 解耦）
    reg [7:0]  pub_cnt;

    //=========================================================
    // 组合：ready/gnt/vld/data
    //=========================================================
    wire rd_accept = corr_rd_req && !rd_in_flight;          // 受理=ready&&req
    assign corr_rd_gnt  = rd_accept;                         // ready 电平
    assign corr_rd_vld  = rd_vld_active;
    assign corr_rd_last = rd_vld_active && (rd_p_cnt == rd_len_q);
    assign corr_rd_data = {rd_word_q[7], rd_word_q[6], rd_word_q[5], rd_word_q[4],
                           rd_word_q[3], rd_word_q[2], rd_word_q[1], rd_word_q[0]};
    assign corr_wr_gnt  = corr_wr_req && wr_ready && !wr_block_now;

    //=========================================================
    // 协议断言（布尔和，一拍累加进 violations）
    //=========================================================
    // [1] 行对齐须查"槽内偏移"：槽基址=slot*2^20，而 2^20%960=256，
    //     槽 1-7 的行首地址(addr%960)天然非 0——直接取模会把正确行首
    //     判为违例（帧#6 读槽 3 时 1080 行全误报）
    wire [23:0] rd_slot_off = corr_rd_addr - {1'b0, corr_src_slot, 20'b0};
    wire v_rd_align = rd_accept && ((rd_slot_off % 24'd960) != 24'd0);  // [1]
    wire v_rd_len   = rd_accept && (corr_rd_len != 7'd119);              // [2]
    wire v_rd_dom   = rd_accept && (!(corr_src_hold_gnt &&
                        (corr_rd_addr[22:20] == {1'b0, corr_src_slot}))); // [3]
    wire v_rd_back  = (!corr_rd_req && rd_req_d && !rd_in_flight);        // [4]
    wire v_rel_busy = corr_src_rel && (rd_in_flight || rd_vld_active);     // [5]
    wire v_rel_gnt  = corr_src_rel && !corr_src_hold_gnt;                 // [6]
    wire v_sl_back  = (!corr_wr_slot_req && slot_req_d && !slot_granted);  // [7]
    wire v_wr_seq   = corr_wr_gnt && (corr_wr_addr != exp_wr_addr);       // [8]
    wire v_wr_dom   = corr_wr_gnt && (corr_wr_addr[22:20] != wr_slot_q);  // [9]
    wire v_com_2cyc = corr_wr_commit && commit_d;                         // [10]
    wire v_com_full = corr_wr_commit &&
                     (exp_wr_addr != wr_base_q + {3'd0, WORDS});           // [11]
    wire v_post_wr  = wr_committed && corr_wr_gnt;                        // [12]

    wire [4:0] viol_sum = v_rd_align + v_rd_len + v_rd_dom + v_rd_back +
                          v_rel_busy + v_rel_gnt + v_sl_back + v_wr_seq +
                          v_wr_dom + v_com_2cyc + v_com_full + v_post_wr;

    integer j;

    //=========================================================
    // 主时序
    //=========================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            latest_slot       <= 2'd0;
            frame_wcnt        <= 2'd0;
            frame_update      <= 1'b0;
            corr_src_hold_gnt <= 1'b0;
            corr_src_slot     <= 2'd0;
            src_req_cnt       <= 8'd0;
            rd_in_flight      <= 1'b0;
            rd_vld_active     <= 1'b0;
            rd_addr_q         <= 24'd0;
            rd_len_q          <= 7'd0;
            rd_wait_cnt       <= 8'd0;
            rd_p_cnt          <= 8'd0;
            rd_req_d          <= 1'b0;
            slot_req_d        <= 1'b0;
            commit_d          <= 1'b0;
            slot_assign       <= 3'd4;
            slot_req_cnt      <= 8'd0;
            slot_granted      <= 1'b0;
            corr_wr_slot_gnt  <= 1'b0;
            corr_wr_slot      <= 3'd0;
            wr_slot_q         <= 3'd0;
            wr_base_q         <= 24'd0;
            exp_wr_addr       <= 24'd0;
            wr_req_cnt        <= 8'd0;
            wr_ready          <= 1'b0;
            wr_committed      <= 1'b0;
            pub_active        <= 1'b0;
            pub_cnt           <= 8'd0;
            corr_pub_pulse    <= 1'b0;
            violations        <= 32'd0;
            for (j = 0; j < 8; j = j + 1) rd_word_q[j] <= 32'd0;
        end else begin
            //-------------------------------------------------
            // 0) 断言累加 + 边沿打拍
            //-------------------------------------------------
            violations <= violations + {27'd0, viol_sum};
            rd_req_d   <= corr_rd_req;
            slot_req_d <= corr_wr_slot_req;
            commit_d   <= corr_wr_commit;

            //-------------------------------------------------
            // 1) C1'：帧完成事件
            //-------------------------------------------------
            frame_update <= ev_publish;
            if (ev_publish) begin
                latest_slot <= ev_slot;
                frame_wcnt  <= ev_slot;
            end

            //-------------------------------------------------
            // 2) D2 granter：req 延迟受理，锁最新帧，保持到 rel
            //-------------------------------------------------
            if (corr_src_hold_req && !corr_src_hold_gnt) begin
                if (src_req_cnt >= SRC_GNT_DLY) begin
                    corr_src_hold_gnt <= 1'b1;
                    corr_src_slot     <= latest_slot;   // 后到优先
                    src_req_cnt       <= 8'd0;
                end else begin
                    src_req_cnt <= src_req_cnt + 8'd1;
                end
            end else if (!corr_src_hold_req) begin
                src_req_cnt <= 8'd0;
            end
            if (corr_src_rel)
                corr_src_hold_gnt <= 1'b0;             // rel 拍解锁

            //-------------------------------------------------
            // 3) C2' 读口：受理 -> 延迟 -> 连续 vld 流
            //    数据预取快照（dword w = 8p+j）
            //-------------------------------------------------
            if (rd_accept) begin
                rd_in_flight  <= 1'b1;
                rd_addr_q     <= corr_rd_addr;
                rd_len_q      <= corr_rd_len;
                rd_wait_cnt   <= 8'd0;
                rd_p_cnt      <= 8'd0;
            end else if (rd_in_flight) begin
                if (!rd_vld_active) begin
                    if (rd_wait_cnt >= RD_DLY) begin
                        rd_vld_active <= 1'b1;
                        for (j = 0; j < 8; j = j + 1)          // 预取拍 0
                            rd_word_q[j] <= ddr_mem[rd_addr_q + j];
                    end else begin
                        rd_wait_cnt <= rd_wait_cnt + 8'd1;
                    end
                end else begin
                    if (rd_p_cnt == rd_len_q) begin
                        // 末拍已输出（last 同拍组合为 1）
                        rd_vld_active <= 1'b0;
                        rd_in_flight  <= 1'b0;
                        rd_p_cnt      <= 8'd0;
                        rd_wait_cnt   <= 8'd0;
                    end else begin
                        // 预取下一拍 p+1 数据
                        for (j = 0; j < 8; j = j + 1)
                            rd_word_q[j] <=
                                ddr_mem[rd_addr_q + {rd_p_cnt, 3'd0} + 8 + j];
                        rd_p_cnt <= rd_p_cnt + 8'd1;
                    end
                end
            end

            //-------------------------------------------------
            // 4) D3 granter：轮换分配 4-7，gnt 单拍
            //-------------------------------------------------
            corr_wr_slot_gnt <= 1'b0;                  // 单拍默认
            if (corr_wr_slot_req) begin
                if (slot_req_cnt >= SLOT_GNT_DLY) begin
                    corr_wr_slot_gnt <= 1'b1;
                    corr_wr_slot    <= slot_assign;
                    wr_slot_q       <= slot_assign;
                    wr_base_q       <= {slot_assign, 20'b0};
                    exp_wr_addr     <= {slot_assign, 20'b0};  // 期望首字
                    slot_assign    <= (slot_assign == 3'd7) ? 3'd4
                                                            : slot_assign + 3'd1;
                    slot_req_cnt   <= 8'd0;
                    slot_granted   <= 1'b1;
                    wr_committed   <= 1'b0;            // 解除 commit 后窗口
                end else begin
                    slot_req_cnt <= slot_req_cnt + 8'd1;
                end
            end else begin
                slot_req_cnt <= 8'd0;
                slot_granted <= 1'b0;
            end

            //-------------------------------------------------
            // 5) C3' 写口：ready 建立 + gnt 拍写入
            //-------------------------------------------------
            if (corr_wr_req) begin
                if (wr_req_cnt >= WR_GNT_DLY) begin
                    wr_ready <= 1'b1;
                end else begin
                    wr_req_cnt <= wr_req_cnt + 8'd1;
                end
            end else begin
                wr_ready   <= 1'b0;
                wr_req_cnt <= 8'd0;
            end
            if (corr_wr_gnt) begin
                ddr_mem[corr_wr_addr] <= corr_wr_data;     // 写后读可见
                exp_wr_addr <= corr_wr_addr + 24'd1;
            end

            //-------------------------------------------------
            // 6) commit / 发布链
            //-------------------------------------------------
            corr_pub_pulse <= 1'b0;                        // 单拍默认
            if (corr_wr_commit) begin
                wr_committed <= 1'b1;    // 断言[12]窗口（下帧 slot gnt 清除）
                pub_active   <= 1'b1;    // 发布链独立启动（解耦，见文件头）
                pub_cnt      <= PUB_DLY; // 8bit 计数承接（PUB_DLY 默认 5）
            end else if (pub_active) begin
                if (pub_cnt > 8'd0) begin
                    pub_cnt <= pub_cnt - 8'd1;
                end else begin
                    corr_pub_pulse <= 1'b1;               // 发布（排空模型）
                    pub_active     <= 1'b0;
                end
            end
        end
    end

endmodule

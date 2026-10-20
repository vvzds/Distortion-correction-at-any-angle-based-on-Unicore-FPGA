//============================================================================
// corr_top_tb.v —— corr_top 顶层联调自校验 TB（stub 结构版，I0-I7）
//----------------------------------------------------------------------------
// 方法    : ModelSim 批仿真自校验（vsim -c -do），无波形依赖；golden 逐字
//           比对 + 协议断言（ideal_link.violations）+ 事件计数锚定推进。
// 加速    : corr_top 例化 CLK_FREQ=12.5MHz（DIV=108，10 倍波特加速，逻辑
//           不变——param_mgr_tb 同款手法）；时钟仍 #4（8ns）。
// 源图    : src_pix(f,y,x) = { x[7:3]^f, y[8:3], x[4:0]^y[4:0] }（RGB565），
//           帧号 f 使各帧 golden 唯一，可检出帧串槽/旧帧残留错误。
// 用例    :
//   I0 复位静默：复位期间与释放后（无参数）全部契约输出为 0、无 X、
//      TX 空闲高、发布计数 0、链路断言 0。
//   I1 门控启动：valid=0 时填帧+发布不启动（无 hold_req）；0x01 合法组
//      下发 -> valid=1 -> 自动 start -> busy/hold_req 起 -> gnt 锁 slot0 ->
//      首个行读 addr=0/len=119；随后 0x02 恒等仿射+使能（帧间隙生效）。
//   I2 身份复制：帧#1 完成 pub#1 -> 校正槽4 逐字==golden(f0)；帧#2（0x02
//      生效帧）-> 槽5==golden 且 dut 内 aff_en=1（G01 回归：恒等系数与
//      使能共存不破坏画面）。
//   I3 Gamma 生效：0x03 三通道（R/G 恒等、B 取反）+0x04 使能 -> 下一帧
//      槽7==golden(f0,B通道取反)。
//   I4 Status 回读（valid=1 宽松）：0x05 回发帧头/版本 0x12/valid 位/
//      pub 计数下限（busy 位采样时刻不定，不比）。
//   I5 跳帧+后到优先：帧#5 锁定后连发 f1/f2/f3（间隔 50 拍），帧#6 的
//      源槽==3（最新帧），槽5==golden(f3)、帧#7==golden(f4)。
//   I6 越界组门控：帧#7 完成后发 fx=64.0（<128.0 下限）-> 越界组滞影子至
//      在途帧#8 rel 拍 swap -> valid=0 -> 帧#9 start 被门控拦截、引擎停机；
//      wait_pub(8) 后精确回读 status==0x0008_0012（pub=8/busy=0/valid=0，
//      stub 与全真件双模式统一）；合法组 -> 自动重启。
//   I7 慢写口+互锁：帧#9（重启帧）写出头/尾各注入 3720 拍阻塞（C3' 上限），
//      帧#10 slot_req 严格晚于帧#9 commit（D3 互锁）；帧#8/#9 槽数据==golden(f4)。
// 判据    : 各用例 PASS/FAIL 打印；末行 err==0 且链路断言 0 时打印
//           === ALL TESTS PASSED (err=0) ===。
// 看门狗  : #300ms（约 37.5M 拍，全程 9 帧 + 阻塞注入总预算 <25M 拍）。
//============================================================================
`timescale 1ns/1ps

module corr_top_tb;

    localparam integer CLK_FREQ_TB = 12_500_000;
    localparam integer DIV = CLK_FREQ_TB / 115_200;     // = 108
    localparam integer SLOT_W = 1048576;                // 2^20 字/槽
    localparam integer FRAME_WORDS = 1_036_800;        // 1080*960

    //--------------------------------------------------------------
    // 时钟 / 复位 / 基础激励
    //--------------------------------------------------------------
    reg  clk = 1'b0;
    reg  rst_n;
    reg  i_uart_rx = 1'b1;
    wire o_uart_tx;

    always #4 clk = ~clk;    // 125 MHz（TB 时轴）

    // TB -> ideal_link 事件/配置
    reg        ev_publish   = 1'b0;
    reg  [1:0] ev_slot      = 2'd0;
    reg        wr_block_now = 1'b0;

    //--------------------------------------------------------------
    // corr_top <-> ideal_link 互连（契约信号）
    //--------------------------------------------------------------
    wire [1:0]  l_frame_wcnt;
    wire        l_frame_update;
    wire        l_hold_req, l_hold_gnt;
    wire [1:0]  l_src_slot;
    wire        l_src_rel;
    wire        l_rd_req;
    wire [23:0] l_rd_addr;
    wire [6:0]  l_rd_len;
    wire        l_rd_gnt, l_rd_vld, l_rd_last;
    wire [255:0] l_rd_data;
    wire        l_slot_req, l_slot_gnt;
    wire [2:0]  l_wr_slot;
    wire        l_commit;
    wire        l_wr_req;
    wire [23:0] l_wr_addr;
    wire [31:0] l_wr_data;
    wire        l_wr_gnt;
    wire        l_pub_pulse;
    wire [31:0] link_viol;

    //--------------------------------------------------------------
    // DUT + 理想链路
    //--------------------------------------------------------------
    corr_top #(
        .CLK_FREQ (CLK_FREQ_TB),
        .SIM_MODE (1'b0)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .i_uart_rx(i_uart_rx), .o_uart_tx(o_uart_tx),
        .i_frame_wcnt(l_frame_wcnt), .i_frame_update(l_frame_update),
        .o_corr_src_hold_req(l_hold_req), .i_corr_src_hold_gnt(l_hold_gnt),
        .i_corr_src_slot(l_src_slot), .o_corr_src_rel(l_src_rel),
        .o_corr_rd_req(l_rd_req), .o_corr_rd_addr(l_rd_addr),
        .o_corr_rd_len(l_rd_len), .i_corr_rd_gnt(l_rd_gnt),
        .i_corr_rd_vld(l_rd_vld), .i_corr_rd_data(l_rd_data),
        .i_corr_rd_last(l_rd_last),
        .o_corr_wr_slot_req(l_slot_req), .i_corr_wr_slot_gnt(l_slot_gnt),
        .i_corr_wr_slot(l_wr_slot), .o_corr_wr_commit(l_commit),
        .o_corr_wr_req(l_wr_req), .o_corr_wr_addr(l_wr_addr),
        .o_corr_wr_data(l_wr_data), .i_corr_wr_gnt(l_wr_gnt),
        .i_corr_pub_pulse(l_pub_pulse)
    );

    ideal_link u_link (
        .clk(clk), .rst_n(rst_n),
        .ev_publish(ev_publish), .ev_slot(ev_slot),
        .wr_block_now(wr_block_now),
        .frame_wcnt(l_frame_wcnt), .frame_update(l_frame_update),
        .corr_src_hold_req(l_hold_req), .corr_src_hold_gnt(l_hold_gnt),
        .corr_src_slot(l_src_slot), .corr_src_rel(l_src_rel),
        .corr_rd_req(l_rd_req), .corr_rd_addr(l_rd_addr),
        .corr_rd_len(l_rd_len), .corr_rd_gnt(l_rd_gnt),
        .corr_rd_vld(l_rd_vld), .corr_rd_data(l_rd_data),
        .corr_rd_last(l_rd_last),
        .corr_wr_slot_req(l_slot_req), .corr_wr_slot_gnt(l_slot_gnt),
        .corr_wr_slot(l_wr_slot), .corr_wr_commit(l_commit),
        .corr_wr_req(l_wr_req), .corr_wr_addr(l_wr_addr),
        .corr_wr_data(l_wr_data), .corr_wr_gnt(l_wr_gnt),
        .corr_pub_pulse(l_pub_pulse),
        .violations(link_viol)
    );

    //--------------------------------------------------------------
    // 看门狗
    //--------------------------------------------------------------
    initial begin
        // 真件版帧周期实测 ~84.3ms/帧（row-0 映射 + C2' 供给节拍），9 帧约 780ms：
        // 看门狗按真件节拍放宽到 1.5s（300ms 系按 stub 版 18.6ms/帧校准）
        #1_500_000_000;
        $display("[%0t] FAIL: watchdog timeout", $time);
        $finish;
    end

    //--------------------------------------------------------------
    // 错误计数 / 事件监测
    //--------------------------------------------------------------
    integer err = 0;

    // 发布脉冲计数（帧账本锚）
    integer pub_cnt = 0;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) pub_cnt <= 0;
        else if (l_pub_pulse) pub_cnt <= pub_cnt + 1;
    end

    // D2 gnt 槽号日志（I5 跳帧/后到优先断言）
    integer gnt_log_cnt = 0;
    reg [1:0] gnt_slot_log [0:31];
    reg hold_gnt_d = 1'b0;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gnt_log_cnt <= 0;  hold_gnt_d <= 1'b0;
        end else begin
            if (l_hold_gnt && !hold_gnt_d) begin
                gnt_slot_log[gnt_log_cnt] <= l_src_slot;
                gnt_log_cnt <= gnt_log_cnt + 1;
            end
            hold_gnt_d <= l_hold_gnt;
        end
    end

    // 帧写出 gnt 计数（I7 尾阻塞注入定位；slot gnt 拍清零）
    reg [20:0] wr_gnt_cnt = 21'd0;
    reg slot_gnt_d = 1'b0;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_gnt_cnt <= 21'd0;  slot_gnt_d <= 1'b0;
        end else begin
            if (l_slot_gnt && !slot_gnt_d)   wr_gnt_cnt <= 21'd0;
            else if (l_wr_req && l_wr_gnt)   wr_gnt_cnt <= wr_gnt_cnt + 21'd1;
            slot_gnt_d <= l_slot_gnt;
        end
    end

    // I1 后台捕获（竞态修复）：param_mgr 在 TB 停止位驱动完前 ~53 拍即交付
    // 末字节，swap→start→hold_req→gnt→撤req→row0 读请求在 send_frame 返回
    // 前已全部完成；hold_req 是数拍短电平、rd_req 是每行 1 拍单脉冲，返回后
    // 电平/脉冲等待必扑空——改为发送前武装（mon_arm=1）、事件锁存、断言。
    reg        mon_arm       = 1'b0;   // 1=捕获中（TB 主流程控制）
    reg        mon_hold_seen = 1'b0;   // hold_req 出现过
    reg        mon_gnt_seen  = 1'b0;   // hold_gnt 出现过
    reg [1:0]  mon_gnt_slot  = 2'd0;   // 首次 gnt 锁存源槽号
    reg        mon_rd_seen   = 1'b0;   // rd_req 出现过
    reg [23:0] mon_rd_addr   = 24'd0;  // 首次 rd_req 锁存地址
    reg [6:0]  mon_rd_len    = 7'd0;   // 首次 rd_req 锁存长度
    always @(posedge clk) begin
        if (mon_arm) begin
            if (l_hold_req)                     mon_hold_seen <= 1'b1;
            if (l_hold_gnt && !mon_gnt_seen) begin
                mon_gnt_seen <= 1'b1;
                mon_gnt_slot <= l_src_slot;   // gnt/slot 同拍更新，次拍读到
            end
            if (l_rd_req && !mon_rd_seen) begin
                mon_rd_seen <= 1'b1;
                mon_rd_addr <= l_rd_addr;      // req/addr/len 同拍更新，次拍读到
                mon_rd_len  <= l_rd_len;
            end
        end
    end

    //--------------------------------------------------------------
    // golden 模型
    //--------------------------------------------------------------
    reg [31:0] golden_mem [0:FRAME_WORDS-1];

    function [15:0] src_pix(input [4:0] f, input [10:0] y, input [10:0] x);
        src_pix = { x[7:3] ^ f, y[8:3], x[4:0] ^ y[4:0] };
    endfunction

    // gamma 模式 0=旁路(en=0 或恒等 LUT)；1=B 通道取反 LUT + en=1
    // （R/G 恒等 LUT 经扩位->查表->截位为无损往返，数学性质已独立验证）
    function [15:0] apply_gamma(input [15:0] p, input integer mode);
        if (mode == 0) apply_gamma = p;
        else           apply_gamma = { p[15:11], p[10:5], ~p[4:0] };
    endfunction

    task gen_golden(input [4:0] f, input integer gmode);
        integer yy, ww;
        reg [15:0] p0, p1;
        begin
            for (yy = 0; yy < 1080; yy = yy + 1) begin
                for (ww = 0; ww < 960; ww = ww + 1) begin
                    p0 = src_pix(f, yy, ww*2);
                    p1 = src_pix(f, yy, ww*2 + 1);
                    p0 = apply_gamma(p0, gmode);
                    p1 = apply_gamma(p1, gmode);
                    golden_mem[yy*960 + ww] = {p1, p0};
                end
            end
        end
    endtask

    // 填源帧到原始槽（模拟一号采集写完成前的数据落盘）
    task fill_frame(input [1:0] slot, input [4:0] f);
        integer yy, ww;
        reg [15:0] p0, p1;
        begin
            for (yy = 0; yy < 1080; yy = yy + 1) begin
                for (ww = 0; ww < 960; ww = ww + 1) begin
                    p0 = src_pix(f, yy, ww*2);
                    p1 = src_pix(f, yy, ww*2 + 1);
                    u_link.ddr_mem[slot*SLOT_W + yy*960 + ww] = {p1, p0};
                end
            end
        end
    endtask

    // 校正槽逐字比对
    task check_slot(input [2:0] slot, input [4:0] f, input integer gmode,
                    input [191:0] name);   // 24 字符：容纳最长标签 "I7 frame9 (back-to-back)"
        integer i, mism;
        reg [31:0] got, expw;
        begin
            gen_golden(f, gmode);
            mism = 0;
            for (i = 0; i < FRAME_WORDS; i = i + 1) begin
                got  = u_link.ddr_mem[slot*SLOT_W + i];
                expw = golden_mem[i];
                if (got !== expw) begin
                    mism = mism + 1;
                    if (mism <= 5)
                        $display("[%0t] FAIL %0s: word %0d got=%h exp=%h",
                                 $time, name, i, got, expw);
                end
            end
            if (mism == 0)
                $display("[%0t] PASS %0s: slot %0d == golden (f=%0d gmode=%0d)",
                         $time, name, slot, f, gmode);
            else begin
                err = err + 1;
                $display("[%0t] FAIL %0s: %0d words mismatch (f=%0d gmode=%0d)",
                         $time, name, mism, f, gmode);
            end
        end
    endtask

    //--------------------------------------------------------------
    // 等待辅助
    //--------------------------------------------------------------
    task wait_cycles(input integer n);
        begin repeat (n) @(posedge clk); end
    endtask

    task wait_valid(input exp_v);
        begin while (dut.w_params_valid !== exp_v) @(posedge clk); end
    endtask

    task wait_busy(input exp_b);
        begin while (dut.w_frame_busy !== exp_b) @(posedge clk); end
    endtask

    task wait_pub(input integer n);
        begin while (pub_cnt < n) @(posedge clk); end
    endtask

    task wait_gnt_cnt(input integer n);
        begin while (gnt_log_cnt < n) @(posedge clk); end
    endtask

    // 发布单拍事件
    task publish_frame(input [1:0] slot);
        begin
            ev_slot    = slot;
            ev_publish = 1'b1;
            @(posedge clk); #1;
            ev_publish = 1'b0;
        end
    endtask

    //--------------------------------------------------------------
    // UART 收发（param_mgr_tb 同款）
    //--------------------------------------------------------------
    task uart_send_byte(input [7:0] b);
        integer k;
        begin
            i_uart_rx <= 1'b0;                 // start bit
            repeat (DIV) @(posedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                i_uart_rx <= b[k];
                repeat (DIV) @(posedge clk);
            end
            i_uart_rx <= 1'b1;                 // stop bit
            repeat (DIV) @(posedge clk);
        end
    endtask

    reg [7:0] frame_buf [0:299];
    integer   frame_len;

    task send_frame(input [7:0] cmd, input [7:0] len_field, input use_bad_chk);
        integer k;
        reg [7:0] chk;
        begin
            chk = 8'h00;
            for (k = 0; k < frame_len; k = k + 1) chk = chk + frame_buf[k];
            uart_send_byte(8'hAA);
            uart_send_byte(8'h55);
            uart_send_byte(cmd);
            uart_send_byte(len_field);
            for (k = 0; k < frame_len; k = k + 1) uart_send_byte(frame_buf[k]);
            if (use_bad_chk) uart_send_byte(chk ^ 8'h5A);
            else             uart_send_byte(chk);
            repeat (10) @(posedge clk);         // inter-frame gap
        end
    endtask

    // 0x01：fx 参数化，其余恒等组（fy=1000/cx=960/cy=540/k1..k4=0）
    // v1.0 用 T3 验收组 k1=-0.1：stub 时代参数不进数据通路无感；真件 core 忠实执行
    // 反畸变映射，与 I2-I7 恒等 golden 必然失配——按"身份复制"判据意图改真恒等
    task load_01_payload(input [31:0] fx_val);
        begin
            frame_buf[0]=fx_val[7:0];   frame_buf[1]=fx_val[15:8];
            frame_buf[2]=fx_val[23:16]; frame_buf[3]=fx_val[31:24];
            frame_buf[4]=8'h00; frame_buf[5]=8'h00; frame_buf[6]=8'hE8;  frame_buf[7]=8'h03;
            frame_buf[8]=8'h00; frame_buf[9]=8'h00; frame_buf[10]=8'hC0; frame_buf[11]=8'h03;
            frame_buf[12]=8'h00; frame_buf[13]=8'h00; frame_buf[14]=8'h1C; frame_buf[15]=8'h02;
            frame_buf[16]=8'h00; frame_buf[17]=8'h00; frame_buf[18]=8'h00; frame_buf[19]=8'h00;
            frame_buf[20]=8'h00; frame_buf[21]=8'h00; frame_buf[22]=8'h00; frame_buf[23]=8'h00;
            frame_buf[24]=8'h00; frame_buf[25]=8'h00; frame_buf[26]=8'h00; frame_buf[27]=8'h00;
            frame_buf[28]=8'h00; frame_buf[29]=8'h00; frame_buf[30]=8'h00; frame_buf[31]=8'h00;
            frame_len = 32;
        end
    endtask

    // 0x02：恒等仿射（a11=a22=1.0）+ 尾字节使能（V1.2 修订 25B）
    task load_02_payload(input [7:0] tail_en);
        begin
            frame_buf[0]=8'h00; frame_buf[1]=8'h00; frame_buf[2]=8'h01; frame_buf[3]=8'h00;  // a11=1.0
            frame_buf[4]=8'h00; frame_buf[5]=8'h00; frame_buf[6]=8'h00; frame_buf[7]=8'h00;  // a12=0
            frame_buf[8]=8'h00; frame_buf[9]=8'h00; frame_buf[10]=8'h00; frame_buf[11]=8'h00; // a21=0
            frame_buf[12]=8'h00; frame_buf[13]=8'h00; frame_buf[14]=8'h01; frame_buf[15]=8'h00; // a22=1.0
            frame_buf[16]=8'h00; frame_buf[17]=8'h00; frame_buf[18]=8'h00; frame_buf[19]=8'h00; // tx=0
            frame_buf[20]=8'h00; frame_buf[21]=8'h00; frame_buf[22]=8'h00; frame_buf[23]=8'h00; // ty=0
            frame_buf[24]=tail_en;                                                            // bit0=aff_en
            frame_len = 25;
        end
    endtask

    // 0x03：256 项 LUT（invert=1 -> 通道取反，否则恒等）
    task load_03_payload(input [7:0] ch, input invert);
        integer i;
        begin
            for (i = 0; i < 256; i = i + 1)
                frame_buf[i] = invert ? (8'hFF - i) : i;   // 8bit 截断
            frame_len = 256;
            // len 字段 = 通道号（send_frame 的 len_field 参数传 ch）
        end
    endtask

    // 0x04：模式字 bit0=gamma_en
    task load_04_payload(input [7:0] bit0);
        begin
            frame_buf[0]=bit0; frame_buf[1]=8'h00; frame_buf[2]=8'h00; frame_buf[3]=8'h00;
            frame_len = 4;
        end
    endtask

    // UART 回读字节（起始沿 + 1.5 bit 到 data0 中心）
    task uart_rx_byte(output [7:0] b);
        integer k;
        begin
            @(negedge o_uart_tx);
            repeat (DIV + DIV/2) @(posedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                b[k] = o_uart_tx;
                repeat (DIV) @(posedge clk);
            end
        end
    endtask

    reg [7:0] rx_buf [0:8];

    // 0x05 回读解析：strict=1 全字比对（I6 停机窗口）；strict=0 宽松（I4）
    task uart_read_status(input [31:0] exp_status, input strict, input [127:0] name);
        integer k;
        reg [31:0] st;
        reg [7:0]  chk;
        begin
            for (k = 0; k < 9; k = k + 1) uart_rx_byte(rx_buf[k]);
            if (rx_buf[0]!==8'hAA || rx_buf[1]!==8'h55 ||
                rx_buf[2]!==8'h05 || rx_buf[3]!==8'h04) begin
                err = err + 1;
                $display("[%0t] FAIL %0s: bad reply header %h %h %h %h",
                         $time, name, rx_buf[0], rx_buf[1], rx_buf[2], rx_buf[3]);
            end else begin
                st  = {rx_buf[7], rx_buf[6], rx_buf[5], rx_buf[4]};
                chk = rx_buf[4] + rx_buf[5] + rx_buf[6] + rx_buf[7];
                if (strict) begin
                    if (st !== exp_status) begin
                        err = err + 1;
                        $display("[%0t] FAIL %0s: status got=%h exp=%h",
                                 $time, name, st, exp_status);
                    end else
                        $display("[%0t] PASS %0s: status=%h", $time, name, st);
                    if (rx_buf[8] !== chk) begin
                        err = err + 1;
                        $display("[%0t] FAIL %0s: reply checksum got=%h exp=%h",
                                 $time, name, rx_buf[8], chk);
                    end
                end else begin
                    // 宽松：版本 / valid 位 / pub 计数下限（busy 与采样时刻不定）
                    if (st[7:0]!==8'h12 || st[8]!==1'b1 || st[31:16] < 16'd4) begin
                        err = err + 1;
                        $display("[%0t] FAIL %0s: loose status check got=%h", $time, name, st);
                    end else
                        $display("[%0t] PASS %0s: loose status=%h", $time, name, st);
                end
            end
        end
    endtask

    //--------------------------------------------------------------
    // 主流程
    //--------------------------------------------------------------
    reg [63:0] i7_t_commit, i7_t_slotreq;
    integer    i;

    initial begin : main
        i7_t_commit = 0;  i7_t_slotreq = 0;

        //==================== I0 复位静默 ====================
        rst_n = 1'b0;
        wait_cycles(10);
        if (l_hold_req!==1'b0 || l_rd_req!==1'b0 || l_wr_req!==1'b0 ||
            l_slot_req!==1'b0 || l_commit!==1'b0) begin
            err = err + 1;
            $display("[%0t] FAIL I0: requests not 0 in reset", $time);
        end
        if (o_uart_tx!==1'b1) begin
            err = err + 1;
            $display("[%0t] FAIL I0: uart_tx not idle high in reset", $time);
        end
        rst_n = 1'b1;
        wait_cycles(1000);
        if (l_hold_req!==1'b0 || l_rd_req!==1'b0 || l_wr_req!==1'b0 ||
            l_slot_req!==1'b0 || l_commit!==1'b0) begin
            err = err + 1;
            $display("[%0t] FAIL I0: requests active with params_valid=0 (gating leak)", $time);
        end
        if (dut.w_frame_busy!==1'b0 || dut.w_params_valid!==1'b0) begin
            err = err + 1;
            $display("[%0t] FAIL I0: busy/valid not 0 after reset", $time);
        end
        if (pub_cnt!==0 || link_viol!==32'd0) begin
            err = err + 1;
            $display("[%0t] FAIL I0: pub_cnt=%0d link_viol=%0d", $time, pub_cnt, link_viol);
        end
        $display("[%0t] I0 done", $time);

        //==================== I1 门控启动 ====================
        fill_frame(2'd0, 5'd0);
        publish_frame(2'd0);
        wait_cycles(2000);
        if (l_hold_req!==1'b0) begin
            err = err + 1;
            $display("[%0t] FAIL I1: hold_req without params (must be gated)", $time);
        end
        // 0x01 合法组 -> valid=1 -> 自动启动
        // 竞态修复：引擎启动序列在 send_frame 返回前已全部完成（见监测器
        // 注释），改发送前武装后台捕获（mon_*）、返回后断言锁存值
        mon_arm = 1'b1;                           // 武装捕获
        load_01_payload(32'h03E8_0000);           // fx=1000.0
        send_frame(8'h01, 8'd32, 1'b0);
        wait_valid(1'b1);
        wait_busy(1'b1);                          // busy 起 -> hold/gnt 必已锁
        // 真件 core：hold gnt 后需先算完 row-0 映射才发首个 C2' 读，时延远大于
        // stub 的即发即读——等首读锁存（上限 2M 拍）再停捕，替代 stub 校准的 20 拍固定窗
        begin : i1_wait_first_rd
            integer w;
            for (w = 0; (w < 2000000) && (mon_rd_seen !== 1'b1); w = w + 1)
                wait_cycles(1);
        end
        mon_arm = 1'b0;                           // 停捕（保持锁存值）
        if (mon_hold_seen!==1'b1) begin
            err = err + 1;
            $display("[%0t] FAIL I1: busy but hold_req never seen", $time);
        end
        if (mon_gnt_seen!==1'b1 || mon_gnt_slot!==2'd0) begin
            err = err + 1;
            $display("[%0t] FAIL I1: locked slot gnt_seen=%0d got=%0d exp=0",
                     $time, mon_gnt_seen, mon_gnt_slot);
        end
        if (mon_rd_seen!==1'b1 || mon_rd_addr!==24'd0 || mon_rd_len!==7'd119) begin
            err = err + 1;
            $display("[%0t] FAIL I1: first read addr=%h len=%0d (exp 0/119)",
                     $time, mon_rd_addr, mon_rd_len);
        end
        // 0x02 恒等仿射+使能（帧#1 busy 中 -> 帧#1 rel 拍 swap -> 帧#2 生效）
        load_02_payload(8'h01);
        send_frame(8'h02, 8'd25, 1'b0);
        $display("[%0t] I1 done (gating/gnt/first-read OK)", $time);

        //==================== I2 身份复制 ====================
        wait_pub(1);
        check_slot(3'd4, 5'd0, 0, "I2 identity copy");
        wait_pub(2);
        if (dut.w_aff_en!==1'b1) begin
            err = err + 1;
            $display("[%0t] FAIL I2: aff_en not swapped to 1", $time);
        end
        check_slot(3'd5, 5'd0, 0, "I2b aff-identity copy");
        $display("[%0t] I2 done", $time);

        //==================== I3 Gamma 生效 ====================
        // 0x03/0x04 在帧#3 busy 中滞留 shadow，帧#3 rel 拍 swap -> 帧#4 生效
        load_03_payload(8'd0, 1'b0); send_frame(8'h03, 8'd0, 1'b0);   // R 恒等
        load_03_payload(8'd1, 1'b0); send_frame(8'h03, 8'd1, 1'b0);   // G 恒等
        load_03_payload(8'd2, 1'b1); send_frame(8'h03, 8'd2, 1'b0);   // B 取反
        load_04_payload(8'h01);      send_frame(8'h04, 8'd4, 1'b0);   // gamma_en=1
        // 帧#3 在 0x03/0x04 滞 shadow 期间完成：数据必须仍为旧参数
        //（恒等、无 gamma）——验证"帧间隙原子切换"而非"逐拍透传"
        wait_pub(3);
        check_slot(3'd6, 5'd0, 0, "I3 frame3 pre-gamma");
        wait_pub(4);
        check_slot(3'd7, 5'd0, 1, "I3 gamma B-invert");
        $display("[%0t] I3 done", $time);

        //==================== I4 Status 回读（valid=1）====================
        frame_len = 0;                             // 必须清零：残留 payload 会使 0x05 坏帧
        send_frame(8'h05, 8'd0, 1'b0);
        uart_read_status(32'h0, 1'b0, "I4 loose status");
        $display("[%0t] I4 done", $time);

        //==================== I5 跳帧 + 后到优先 ====================
        wait_gnt_cnt(5);                       // 帧#5 已锁源（f0），此后连发才安全
        fill_frame(2'd1, 5'd1); publish_frame(2'd1);
        wait_cycles(50);
        fill_frame(2'd2, 5'd2); publish_frame(2'd2);
        wait_cycles(50);
        fill_frame(2'd3, 5'd3); publish_frame(2'd3);
        // f4 发布时机：帧#7 锁源发生在帧#6 core rel 拍（早于 pub#6 约
        // 8.3ms 写出耗时），故 f4 必须在帧#6 gnt 后、帧#7 gnt 前发布——
        // 锚 gnt 而非 pub
        wait_gnt_cnt(6);                       // 帧#6 gnt：已锁 f3，帧#7 未锁
        if (l_frame_wcnt!==2'd3) begin         // f4 未发布，wcnt 仍=3（f3 最新）
            err = err + 1;
            $display("[%0t] FAIL I5: frame_wcnt got=%0d exp=3", $time, l_frame_wcnt);
        end
        fill_frame(2'd0, 5'd4); publish_frame(2'd0);   // f4 -> 帧#7 用
        wait_pub(6);                           // 帧#5(f0) pub#5 -> 帧#6(f3) pub#6
        if (gnt_slot_log[5]!==2'd3) begin
            err = err + 1;
            $display("[%0t] FAIL I5: frame6 locked slot got=%0d exp=3 (latest-first)",
                     $time, gnt_slot_log[5]);
        end
        check_slot(3'd4, 5'd0, 1, "I5 frame5");   // 帧#5 落槽4
        check_slot(3'd5, 5'd3, 1, "I5 frame6");   // 帧#6(f3) 落槽5
        wait_pub(7);
        check_slot(3'd6, 5'd4, 1, "I5 frame7");
        $display("[%0t] I5 done", $time);

        //==================== I6 越界组门控 ====================
        wait_gnt_cnt(7);                       // gnt#7 早在 I5 内满足（即时返回）；自由连续下帧#8 已在 pub#7 前启动
        load_01_payload(32'h0040_0000);        // fx=64.0 < G02 下限 128.0
        send_frame(8'h01, 8'd32, 1'b0);
        wait_pub(7);                           // 帧#7 正常完成（旧参数）
        wait_valid(1'b0);                      // 帧#8 rel 拍 swap -> valid=0（帧#9 start 随后被门控拦截）
        // 竞态消除（corr_top V1.0.1）+ core params_ok 双保险：帧#9 start
        // 被确定性拦截，引擎在帧#8 后停机（无越界帧跑过，双模式一致）。
        wait_busy(1'b0);                       // core 停机确认（帧#9 未启动）
        wait_pub(8);                           // 等 in-flight 帧#8 写出收尾（pub#8），链路全静止
        wait_cycles(5000);
        if (l_hold_req!==1'b0 || l_rd_req!==1'b0 || l_slot_req!==1'b0) begin
            err = err + 1;
            $display("[%0t] FAIL I6: engine not stopped with params_valid=0", $time);
        end
        // 精确回读（完全停机+写出收尾后 status 确定）：pub=8/busy=0/valid=0/
        // version=0x12。pub#8 已被 wait_pub(8) 观测，判据与 rel->pub 写出滞后
        // 无关（stub 约8.5ms/真件约0.2ms），双模式统一；旧判据 0007_0012 废止
        frame_len = 0;                             // 必须清零：残留 payload 会使 0x05 坏帧
        send_frame(8'h05, 8'd0, 1'b0);
        uart_read_status({16'd8, 6'd0, 1'b0, 1'b0, 8'h12}, 1'b1, "I6 exact status");
        // 合法组 -> 自动重启
        load_01_payload(32'h03E8_0000);
        send_frame(8'h01, 8'd32, 1'b0);
        wait_valid(1'b1);
        wait_busy(1'b1);
        $display("[%0t] I6 done (stop + exact status + restart)", $time);

        //==================== I7 慢写口 + D3 互锁 ====================
        // 帧#9（重启帧）写出起点 -> 头阻塞 3720 拍（C3' 上限；wait_pub(8) 已确保
        //   帧#8 写出收尾，此处首个 wr_req 即帧#9 写出真起点）
        begin : i7_wrreq
            forever begin
                @(posedge clk); #1;
                if (l_wr_req === 1'b1) disable i7_wrreq;
            end
        end
        wr_block_now = 1'b1;
        wait_cycles(3720);
        wr_block_now = 1'b0;
        // 帧#9 写到末 10 字 -> 尾阻塞 3720 拍（commit 推迟，加大互锁窗口）
        while (wr_gnt_cnt < 1036790) @(posedge clk);
        wr_block_now = 1'b1;
        wait_cycles(3720);
        wr_block_now = 1'b0;
        // 互锁断言：帧#9 commit 先于帧#10 slot_req（自由连续帧#10 在帧#9 rel 拍启动）
        begin : i7_commit
            forever begin
                @(posedge clk); #1;
                if (l_commit === 1'b1) disable i7_commit;
            end
        end
        i7_t_commit = $time;
        begin : i7_slotreq
            forever begin
                @(posedge clk); #1;
                if (l_slot_req === 1'b1) disable i7_slotreq;
            end
        end
        i7_t_slotreq = $time;
        if (i7_t_slotreq <= i7_t_commit) begin
            err = err + 1;
            $display("[%0t] FAIL I7: frame10 slot_req(%0d) not strictly after frame9 commit(%0d)",
                     $time, i7_t_slotreq, i7_t_commit);
        end
        wait_pub(9);
        check_slot(3'd7, 5'd4, 1, "I7 frame8 (free-run)");
        check_slot(3'd4, 5'd4, 1, "I7 frame9 (slow write)");
        $display("[%0t] I7 done (interlock: slotreq@%0d > commit@%0d)",
                $time, i7_t_slotreq, i7_t_commit);

        //==================== 汇总 ====================
        wait_cycles(100);
        if (link_viol !== 32'd0) begin
            err = err + 1;
            $display("[%0t] FAIL: link protocol violations = %0d", $time, link_viol);
        end
        if (pub_cnt !== 9) begin
            err = err + 1;
            $display("[%0t] FAIL: pub_cnt=%0d exp=9", $time, pub_cnt);
        end
        if (err == 0)
            $display("=== ALL TESTS PASSED (err=0) ===");
        else
            $display("=== TESTS FAILED (err=%0d, link_viol=%0d) ===", err, link_viol);
        $finish;
    end

endmodule

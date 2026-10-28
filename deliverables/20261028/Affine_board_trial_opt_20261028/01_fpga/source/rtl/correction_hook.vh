// Engine mounting point. Production delivery has no correction algorithm.
// Attach undistort_core here using corr_clk/corr_rst_n and the documented wires.
// With RD_SLOT_BASE=4 and this idle hook, HDMI timing is valid but picture is
// black until a full corrected frame is committed and drained.

// 2026-10-18 设计方接入：生产模式 4 实例化校正子系统（corr_top 全真件，G3 版）。
// 端口按 integ_ws corr_top.v 实际端口表映射顶层 corr_* 契约信号；
// UART 接板载 CP2102（rx=B24/tx=C24）。corr_protocol_error 顶层无对应端口，维持无驱动。
// 原空置 assign 版已由一号 zip 归档（SHA256 A8EC112F…），此处为宿主工程唯一功能接入点。
corr_top u_corr_top (
    .clk                 (corr_clk),
    .rst_n               (corr_rst_n),
    .i_uart_rx           (uart_rx),
    .o_uart_tx           (uart_tx),
    .i_frame_wcnt        (o_frame_wcnt),
    .i_frame_update      (o_frame_update),
    .o_corr_src_hold_req (corr_src_hold_req),
    .i_corr_src_hold_gnt (corr_src_hold_gnt),
    .i_corr_src_slot     (corr_src_slot),
    .o_corr_src_rel      (corr_src_rel),
    .o_corr_rd_req       (corr_rd_req),
    .o_corr_rd_addr      (corr_rd_addr),
    .o_corr_rd_len       (corr_rd_len),
    .i_corr_rd_gnt       (corr_rd_gnt),
    .i_corr_rd_vld       (corr_rd_vld),
    .i_corr_rd_data      (corr_rd_data),
    .i_corr_rd_last      (corr_rd_last),
    .o_corr_wr_slot_req  (corr_wr_slot_req),
    .i_corr_wr_slot_gnt  (corr_wr_slot_gnt),
    .i_corr_wr_slot      (corr_wr_slot),
    .o_corr_wr_commit    (corr_wr_commit),
    .o_corr_wr_req       (corr_wr_req),
    .o_corr_wr_addr      (corr_wr_addr),
    .o_corr_wr_data      (corr_wr_data),
    .i_corr_wr_gnt       (corr_wr_gnt),
    .i_corr_pub_pulse    (corr_pub_pulse)
);

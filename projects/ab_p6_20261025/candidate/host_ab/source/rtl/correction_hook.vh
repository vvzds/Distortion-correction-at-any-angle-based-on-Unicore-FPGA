// Real correction subsystem, single 125 MHz DDR clock domain.
corr_top #(.CLK_FREQ(125_000_000),.SIM_MODE(0)) u_correction (
    .clk(corr_clk),.rst_n(corr_rst_n),
    .i_uart_rx(uart_rx),.o_uart_tx(uart_tx),
    .i_frame_wcnt(o_frame_wcnt),.i_frame_update(o_frame_update),
    .o_corr_src_hold_req(corr_src_hold_req),
    .i_corr_src_hold_gnt(corr_src_hold_gnt),.i_corr_src_slot(corr_src_slot),
    .o_corr_src_rel(corr_src_rel),
    .o_corr_rd_req(corr_rd_req),.o_corr_rd_addr(corr_rd_addr),
    .o_corr_rd_len(corr_rd_len),.i_corr_rd_gnt(corr_rd_gnt),
    .i_corr_rd_vld(corr_rd_vld),.i_corr_rd_data(corr_rd_data),
    .i_corr_rd_last(corr_rd_last),
    .o_corr_wr_slot_req(corr_wr_slot_req),
    .i_corr_wr_slot_gnt(corr_wr_slot_gnt),.i_corr_wr_slot(corr_wr_slot),
    .o_corr_wr_commit(corr_wr_commit),.o_corr_wr_req(corr_wr_req),
    .o_corr_wr_addr(corr_wr_addr),.o_corr_wr_data(corr_wr_data),
    .i_corr_wr_gnt(corr_wr_gnt),.i_corr_pub_pulse(corr_pub_pulse)
);

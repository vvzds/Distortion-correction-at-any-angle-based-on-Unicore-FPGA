// Engine mounting point. Production delivery has no correction algorithm.
// Attach undistort_core here using corr_clk/corr_rst_n and the documented wires.
// With RD_SLOT_BASE=4 and this idle hook, HDMI timing is valid but picture is
// black until a full corrected frame is committed and drained.
assign corr_src_hold_req=1'b0;
assign corr_src_rel=1'b0;
assign corr_rd_req=1'b0;
assign corr_rd_addr=24'd0;
assign corr_rd_len=7'd119;
assign corr_wr_req=1'b0;
assign corr_wr_addr=24'd0;
assign corr_wr_data=32'd0;
assign corr_wr_slot_req=1'b0;
assign corr_wr_commit=1'b0;

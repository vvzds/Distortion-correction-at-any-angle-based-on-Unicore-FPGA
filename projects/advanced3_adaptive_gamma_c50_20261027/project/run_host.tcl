cd [file dirname [info script]]
# ---------------------------------------------------------------------------
# Batch build script (PDS 2022.2): rebuild hdmi_ddr_ov5640_top through routed timing and bitstream.
# File list taken from the project file HDMI_DDR3_OV5640_test.pds.
# ---------------------------------------------------------------------------
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676

add_design "source/rtl/hdmi_ddr_ov5640_top.v"
add_design "source/rtl/raw8_to_rgb565.v"
add_design "source/rtl/frame_bank_ctrl.v"
# 设计方校正子系统（corr_top 全真件，G3 版，2026-10-18 接入）
add_design "source/rtl/corr_subsys/corr_top.v"
add_design "source/rtl/corr_subsys/param_mgr.v"
add_design "source/rtl/corr_subsys/gamma_lut.v"
add_design "source/rtl/corr_subsys/adaptive_gamma.v"
add_design "source/rtl/corr_subsys/adaptive_gamma_curve.v"
add_design "source/rtl/corr_subsys/undistort_map.v"
add_design "source/rtl/corr_subsys/undistort_cache_ab.v"
add_design "source/rtl/corr_subsys/undistort_bilinear.v"
add_design "source/rtl/corr_subsys/undistort_core.v"
add_design "source/rtl/corr_subsys/rect_wr_if.v"
add_design "source/rtl/corr_read_bridge.v"
add_design "source/rtl/corr_write_pack.v"
add_design "source/rtl/corr_write_arb.v"
add_design "source/rtl/corr_slot_ctrl.v"

add_design "source/rtl/fram_buf.v"
add_design "source/rtl/i2c_com.v"
add_design "source/rtl/iic_dri.v"
add_design "source/rtl/ms72xx_ctl.v"
add_design "source/rtl/ms7200_ctl.v"
add_design "source/rtl/ms7210_ctl.v"
add_design "source/rtl/power_on_delay.v"
add_design "source/rtl/rd_buf.v"
add_design "source/rtl/rd_ctrl.v"
add_design "source/rtl/reg_config.v"
add_design "source/rtl/sync_vg.v"
add_design "source/rtl/wr_buf.v"
add_design "source/rtl/wr_cmd_trans.v"
add_design "source/rtl/wr_ctrl.v"
add_design "source/rtl/wr_rd_ctrl_top.v"

add_design "ipcore/pll/pll.idf"
add_design "ipcore/rd_fram_buf/rd_fram_buf.idf"
add_design "ipcore/wr_fram_buf/wr_fram_buf.idf"
add_design "ipcore/ddr3_test/ddr3_test.idf"

add_constraint "HDMI_DDR3_OV5640_test.fdc"

compile -top_module hdmi_ddr_ov5640_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
puts "G7_PHASE=DEV_MAP_DONE"
pnr -gplace_seed 7 -groute_seed 7 -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 20
puts "G7_PHASE=PNR_DONE"
report_timing -max_path 30

puts "G7_PHASE=FINISHED"

exit

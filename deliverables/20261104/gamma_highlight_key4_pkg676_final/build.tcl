cd [file dirname [info script]]
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design "source/rtl/hdmi_ddr_ov5640_top.v"
add_design "source/rtl/raw8_to_rgb565.v"
add_design "source/rtl/frame_bank_ctrl.v"
add_design "source/rtl/corr_read_bridge.v"
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
add_design "source/rtl/projective_divide.v"
add_design "source/rtl/mul32_pipe.v"
add_design "source/rtl/brown_map.v"
add_design "source/rtl/patch_store.v"
add_design "source/rtl/bilinear_rgb.v"
add_design "source/rtl/adaptive_gamma.v"
add_design "source/rtl/tile_engine.v"
add_design "source/rtl/tile_write_pack.v"
add_design "source/rtl/uart_phy.v"
add_design "source/rtl/host_control.v"
add_design "source/rtl/feature_key_control.v"
add_design "source/rtl/bno_spi_byte.v"
add_design "source/rtl/bno085_bridge.v"
add_design "source/rtl/imu_projective_map.v"
add_design "source/rtl/display_denoise.v"
add_design "source/rtl/display_sharpen.v"
add_design "source/rtl/video_osd.v"
add_design "ipcore/pll/pll.idf"
add_design "ipcore/rd_fram_buf/rd_fram_buf.idf"
add_design "ipcore/wr_fram_buf/wr_fram_buf.idf"
add_design "ipcore/ddr3_test/ddr3_test.idf"
add_constraint "HDMI_DDR3_OV5640_test.fdc"
compile -top_module hdmi_ddr_ov5640_top
synthesize -ads -selected_syn_tool_opt 2
if {[info exists ::env(FPGA_SYNTH_ONLY)] && $::env(FPGA_SYNTH_ONLY) eq "1"} {exit}
dev_map
if {[info exists ::env(FPGA_PNR_SEED)]} {
    pnr -gplace_seed $::env(FPGA_PNR_SEED) -groute_seed $::env(FPGA_PNR_SEED) -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 20
} else {pnr}
report_timing -max_path 30
gen_bit_stream

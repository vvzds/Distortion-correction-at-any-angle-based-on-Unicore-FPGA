# OFFLINE_ANALYSIS_ONLY; UART LOC unresolved; no bitstream; seed=2
cd [file dirname [info script]]
# ---------------------------------------------------------------------------
# Batch build script (PDS 2022.2): rebuild hdmi_ddr_ov5640_top + bitstream.
# File list taken from the project file HDMI_DDR3_OV5640_test.pds.
# ---------------------------------------------------------------------------
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676

add_design "source/rtl/hdmi_ddr_ov5640_top.v"
add_design "source/rtl/raw8_to_rgb565.v"
add_design "source/rtl/frame_bank_ctrl.v"
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

add_design "source/rtl/corr_top.v"
add_design "source/rtl/param_mgr.v"
add_design "source/rtl/gamma_lut.v"
add_design "source/rtl/rect_wr_if.v"
add_design "source/rtl/undistort_core.v"
add_design "source/rtl/undistort_map.v"
add_design "source/rtl/undistort_bilinear.v"
add_design "source/rtl/undistort_cache_ab.v"

add_constraint "HDMI_DDR3_OV5640_test.fdc"

compile -top_module hdmi_ddr_ov5640_top
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -gplace_seed 2 -groute_seed 2
report_timing -max_path 20 -nworst 1
# Preserve unrestricted report/CSV; focused reports are diagnostics only.
file rename report_timing report_timing_full_saved
file copy -force multiseed_summary.csv multiseed_summary_full_saved.csv
puts "P3_MAP_DIAG_BEGIN"
if {[catch {report_timing -from [get_cells {u_correction/u_core/u_map/*}] -max_path 20 -nworst 1} diag_error]} {
    puts "P3_MAP_DIAG_FAILED: $diag_error"
} else {
    puts "P3_MAP_DIAG_COMPLETED"
}
if {[file exists report_timing]} {file rename report_timing report_timing_map_diagnostic}
puts "P3_CACHE_FROM_DIAG_BEGIN"
if {[catch {report_timing -from [get_cells {u_correction/u_core/u_cache/*}] -max_path 20 -nworst 1} diag_error]} {
    puts "P3_CACHE_FROM_DIAG_FAILED: $diag_error"
} else {
    puts "P3_CACHE_FROM_DIAG_COMPLETED"
}
if {[file exists report_timing]} {file rename report_timing report_timing_cache_from_diagnostic}
puts "P3_CACHE_TO_DIAG_BEGIN"
if {[catch {report_timing -to [get_cells {u_correction/u_core/u_cache/*}] -max_path 20 -nworst 1} diag_error]} {
    puts "P3_CACHE_TO_DIAG_FAILED: $diag_error"
} else {
    puts "P3_CACHE_TO_DIAG_COMPLETED"
}
if {[file exists report_timing]} {file rename report_timing report_timing_cache_to_diagnostic}
file rename report_timing_full_saved report_timing
file copy -force multiseed_summary_full_saved.csv multiseed_summary.csv
puts "P3_UNRESTRICTED_REPORT_RESTORED"
exit

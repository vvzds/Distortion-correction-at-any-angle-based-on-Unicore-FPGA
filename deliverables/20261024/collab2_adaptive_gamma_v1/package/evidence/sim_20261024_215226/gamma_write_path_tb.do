onerror {quit -code 2 -f}
vlog -vlog01compat rtl/adaptive_gamma_curve.v rtl/adaptive_gamma.v rtl/gamma_lut.v rtl/corr_top.v reference/param_mgr.v reference/rect_wr_if.v reference/undistort_core.v reference/undistort_map.v reference/undistort_line_cache.v reference/undistort_bilinear.v sim/ideal_link.v sim/gamma_write_path_tb.v
vopt work.gamma_write_path_tb +acc -o gamma_write_path_tb_opt
vsim work.gamma_write_path_tb_opt
onfinish stop
run -all
quit -code 0 -f

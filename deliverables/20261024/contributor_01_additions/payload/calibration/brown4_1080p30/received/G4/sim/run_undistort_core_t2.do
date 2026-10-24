if {![file exists work/_info]} { vlib work }
vlog -work work ../source/rtl/undistort_map.v ../source/rtl/undistort_line_cache.v ../source/rtl/undistort_bilinear.v ../source/rtl/undistort_core.v
vlog -work work undistort_core_t2_tb.v
vopt work.undistort_core_t2_tb +acc -o core_t2_acc
vsim work.core_t2_acc
onfinish stop
run -all
quit -f

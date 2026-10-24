if {![file exists work/_info]} { vlib work }
vlog -work work ../source/rtl/undistort_map.v ../source/rtl/undistort_line_cache.v ../source/rtl/undistort_bilinear.v ../source/rtl/undistort_core.v
vlog -work work undistort_core_golden_tb.v
vopt work.undistort_core_golden_tb +acc -o core_golden_acc
vsim work.core_golden_acc
onfinish stop
run -all
quit -f

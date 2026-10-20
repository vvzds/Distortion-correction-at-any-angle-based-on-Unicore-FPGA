if {![file exists work/_info]} { vlib work }
vlog -work work ../source/rtl/undistort_line_cache.v
vlog -work work undistort_line_cache_tb.v
vopt work.undistort_line_cache_tb +acc -o line_cache_acc
vsim work.line_cache_acc
onfinish stop
run -all
quit -f

if {![file exists work/_info]} { vlib work }
vlog -work work ../source/rtl/undistort_map.v
vlog -work work undistort_map_tb.v
vopt work.undistort_map_tb +acc -o map_acc
vsim work.map_acc
onfinish stop
run -all
quit -f

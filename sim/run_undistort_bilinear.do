if {![file exists work/_info]} { vlib work }
vlog -work work ../source/rtl/undistort_bilinear.v
vlog -work work undistort_bilinear_tb.v
vopt work.undistort_bilinear_tb +acc -o bilinear_acc
vsim work.bilinear_acc
onfinish stop
run -all
quit -f

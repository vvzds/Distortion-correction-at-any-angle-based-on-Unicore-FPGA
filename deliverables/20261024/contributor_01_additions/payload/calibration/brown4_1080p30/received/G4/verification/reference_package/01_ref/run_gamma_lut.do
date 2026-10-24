if {![file exists work/_info]} { vlib work }
vlog -work work ../source/rtl/gamma_lut.v
vlog -work work gamma_lut_tb.v
vsim work.gamma_lut_tb
run -all
quit -f

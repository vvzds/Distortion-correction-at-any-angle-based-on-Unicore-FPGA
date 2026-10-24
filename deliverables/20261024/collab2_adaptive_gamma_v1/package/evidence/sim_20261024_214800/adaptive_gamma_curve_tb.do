onerror {quit -code 2 -f}
vlib work
vlog -vlog01compat rtl/adaptive_gamma_curve.v rtl/adaptive_gamma.v sim/adaptive_gamma_curve_tb.v
vsim work.adaptive_gamma_curve_tb
onfinish stop
run -all
quit -code 0 -f

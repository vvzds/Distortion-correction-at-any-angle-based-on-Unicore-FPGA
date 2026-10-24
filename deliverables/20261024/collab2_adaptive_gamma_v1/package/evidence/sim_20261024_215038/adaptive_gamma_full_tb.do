onerror {quit -code 2 -f}
vlog -vlog01compat rtl/adaptive_gamma_curve.v rtl/adaptive_gamma.v sim/adaptive_gamma_full_tb.v
vopt work.adaptive_gamma_full_tb +acc -o adaptive_gamma_full_tb_opt
vsim work.adaptive_gamma_full_tb_opt
onfinish stop
run -all
quit -code 0 -f

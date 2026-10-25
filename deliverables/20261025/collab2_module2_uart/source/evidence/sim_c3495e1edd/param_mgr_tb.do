onerror {quit -code 2 -f}
vlib work
vlog -vlog01compat reference/param_mgr.v reference/param_mgr_tb.v
vopt work.param_mgr_tb +acc -o param_mgr_tb_opt
vsim work.param_mgr_tb_opt
onfinish stop
run -all
quit -code 0 -f

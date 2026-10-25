onerror {quit -code 2 -f}
vlog -vlog01compat reference/param_mgr.v tb/param_mgr_extended_tb.v
vopt work.param_mgr_extended_tb +acc -o param_mgr_extended_tb_opt
vsim work.param_mgr_extended_tb_opt
onfinish stop
run -all
quit -code 0 -f

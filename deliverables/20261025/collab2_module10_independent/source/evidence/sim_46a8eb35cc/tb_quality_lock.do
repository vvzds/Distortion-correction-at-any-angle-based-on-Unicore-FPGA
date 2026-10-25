onerror {quit -code 2 -f}
vlib work
vlog -vlog01compat rtl/ov5640_quality_lock.v rtl/ov5640_sccb_access.v rtl/ov5640_quality_control.v tb/tb_quality_lock.v
vopt work.tb_quality_lock +acc -o tb_quality_lock_opt
vsim work.tb_quality_lock_opt
onfinish stop
run -all
quit -code 0 -f

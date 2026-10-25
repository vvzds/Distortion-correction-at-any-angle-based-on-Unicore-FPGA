onerror {quit -code 2 -f}
vlog -vlog01compat rtl/ov5640_quality_lock.v rtl/ov5640_sccb_access.v tb/tb_sccb_access.v
vopt work.tb_sccb_access +acc -o tb_sccb_access_opt
vsim work.tb_sccb_access_opt
onfinish stop
run -all
quit -code 0 -f

# param_mgr ModelSim 批处理仿真脚本（vsim -c -do run_param_mgr.do）
# 用法：在 sim 目录下执行  vsim -c -do run_param_mgr.do
# 产物：transcript（含全部 PASS/FAIL 判决）

if {![file exists work/_info]} { vlib work }
vlog -work work ../source/rtl/param_mgr.v
vlog -work work param_mgr_tb.v
vsim work.param_mgr_tb
run -all
quit -f

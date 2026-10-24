# run_corr_top_full.do —— corr_top 顶层全真件联调批仿真
# 用法：vsim -c -do run_corr_top_full.do（工作目录 = 本文件所在 tb 目录）
# 前置：协作者交付的 undistort_core 4 文件套件（core/map/line_cache/bilinear）
#       与 rect_wr_if.v 已放入 source/rtl/（与交付原件哈希核验一致）。
# 说明：与 run_corr_top_stub.do 仅差 core（4 文件）与 wr_if 的编译行；
#       ideal_link.v 协议断言与 TB 用例（I0-I7）对真件同样全部生效。

if {![file exists work/_info]} { vlib work }
vlog -work work ../source/rtl/corr_top.v
vlog -work work ../source/rtl/param_mgr.v
vlog -work work ../source/rtl/gamma_lut.v
vlog -work work ../source/rtl/undistort_map.v
vlog -work work ../source/rtl/undistort_line_cache.v
vlog -work work ../source/rtl/undistort_bilinear.v
vlog -work work ../source/rtl/undistort_core.v
vlog -work work ../source/rtl/rect_wr_if.v
vlog -work work ../sim_models/ideal_link.v
vlog -work work corr_top_tb.v
vsim work.corr_top_tb
run -all
quit -f

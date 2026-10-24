# 历史失败流程，仅留作G1复核追溯，不再作为可执行P&R方案。
# SP6.4实测：禁用IO插入报DRC-0001；启用IO插入则898端口超过300个IO，报DRC-0018。
# 纯核只运行pds_core.tcl综合；物理P&R须在真实corr_top集成工程完成。
error "Obsolete standalone-core P&R flow. Use verification/pds_core.tcl for synthesis; run P&R in the real integrated corr_top project."
set_arch -family Logos2 -device PG2L100H -package FBG676 -speedgrade -6
add_design source/rtl/undistort_map.v
add_design source/rtl/undistort_line_cache.v
add_design source/rtl/undistort_bilinear.v
add_design source/rtl/undistort_core.v
compile -top_module undistort_core
synthesize -ads -disable_io_insertion -frequency 125
dev_map
pnr -report_timing
report_timing -max_path 50 -nworst 3
exit

cd [file dirname [info script]]
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design "strip_reorder.v"
add_constraint "strip_reorder.fdc"
compile -top_module strip_reorder
synthesize -ads -selected_syn_tool_opt 2
dev_map
pnr -gplace_seed 7 -groute_seed 7 -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 20
report_timing -max_path 30
puts "C64_PHASE=ROUTE_TIMING_DONE"
exit

cd [file dirname [info script]]
set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design "strip_reorder.v"
compile -top_module strip_reorder
synthesize -ads -selected_syn_tool_opt 2
dev_map
puts "C64_PHASE=DEV_MAP_DONE"
exit

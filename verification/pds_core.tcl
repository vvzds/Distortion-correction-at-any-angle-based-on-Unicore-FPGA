set_arch -family Logos2 -device PG2L100H -package FBG676 -speedgrade -6
add_design source/rtl/undistort_map.v
add_design source/rtl/undistort_line_cache.v
add_design source/rtl/undistort_bilinear.v
add_design source/rtl/undistort_core.v
compile -top_module undistort_core
synthesize -ads -disable_io_insertion -frequency 125
exit

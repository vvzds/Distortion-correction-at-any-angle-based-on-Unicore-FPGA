set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
report_timing -input_db_file {Y:/physical/host_seed2/place_route/hdmi_ddr_ov5640_top_pnr.adf} -to [get_cells {u_correction/u_core/u_cache/last_use*}] -delay_type min_max -max_path 20 -nworst 1
exit

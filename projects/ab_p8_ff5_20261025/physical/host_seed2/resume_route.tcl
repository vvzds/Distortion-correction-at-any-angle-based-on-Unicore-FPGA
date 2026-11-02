set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
pnr -input_db_file {Q:/device_map/hdmi_ddr_ov5640_top_map.adf} -input_place_db_file {Q:/place_route/hdmi_ddr_ov5640_top_plc.adf} -gplace_seed 2 -groute_seed 2
report_timing -max_path 20 -nworst 1
exit

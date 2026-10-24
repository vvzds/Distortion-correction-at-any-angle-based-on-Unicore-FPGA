# Preserve unrestricted report/CSV; focused reports are diagnostics only.
file rename report_timing report_timing_full_saved
file copy -force multiseed_summary.csv multiseed_summary_full_saved.csv
puts "P3_MAP_DIAG_BEGIN"
if {[catch {report_timing -from [get_cells {u_correction/u_core/u_map/*}] -max_path 20 -nworst 1} diag_error]} {
    puts "P3_MAP_DIAG_FAILED: $diag_error"
} else {
    puts "P3_MAP_DIAG_COMPLETED"
}
if {[file exists report_timing]} {file rename report_timing report_timing_map_diagnostic}
puts "P3_CACHE_FROM_DIAG_BEGIN"
if {[catch {report_timing -from [get_cells {u_correction/u_core/u_cache/*}] -max_path 20 -nworst 1} diag_error]} {
    puts "P3_CACHE_FROM_DIAG_FAILED: $diag_error"
} else {
    puts "P3_CACHE_FROM_DIAG_COMPLETED"
}
if {[file exists report_timing]} {file rename report_timing report_timing_cache_from_diagnostic}
puts "P3_CACHE_TO_DIAG_BEGIN"
if {[catch {report_timing -to [get_cells {u_correction/u_core/u_cache/*}] -max_path 20 -nworst 1} diag_error]} {
    puts "P3_CACHE_TO_DIAG_FAILED: $diag_error"
} else {
    puts "P3_CACHE_TO_DIAG_COMPLETED"
}
if {[file exists report_timing]} {file rename report_timing report_timing_cache_to_diagnostic}
file rename report_timing_full_saved report_timing
file copy -force multiseed_summary_full_saved.csv multiseed_summary.csv
puts "P3_UNRESTRICTED_REPORT_RESTORED"

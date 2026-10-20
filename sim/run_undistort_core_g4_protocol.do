onerror {quit -code 1 -f}
if {![file exists g4_protocol_work/_info]} {vlib g4_protocol_work}
vlog -work g4_protocol_work ../source/rtl/undistort_map.v ../source/rtl/undistort_line_cache.v ../source/rtl/undistort_bilinear.v ../source/rtl/undistort_core.v undistort_core_g4_protocol_tb.v
foreach mode {0 1} {
    vopt -work g4_protocol_work g4_protocol_work.undistort_core_g4_protocol_tb -gMODE=$mode +acc -o g4_protocol_$mode
    if {$mode == 0} {set path core_g4_protocol_result.txt} else {set path core_g4_protocol_sim_result.txt}
    file delete -force $path
    vsim g4_protocol_work.g4_protocol_$mode
    onfinish stop
    run -all
    quit -sim
    if {![file exists $path]} {error "Missing result $path"}
    set f [open $path r]
    set result [read $f]
    close $f
    puts $result
    if {[regexp {FAIL|TIMEOUT} $result] || ![string match {*ALL TESTS PASSED (err=0)*} $result]} {error "G4 protocol test failed"}
}
# 负向突变：在READ_ADDR强制提前req，必须由同一检查器明确报FAIL。
vopt -work g4_protocol_work g4_protocol_work.undistort_core_g4_protocol_tb -gMODE=0 -gFAULT=1 +acc -o g4_protocol_fault
file delete -force core_g4_fault_injection_result.txt
vsim g4_protocol_work.g4_protocol_fault
onfinish stop
run -all
quit -sim
set f [open core_g4_fault_injection_result.txt r]
set fault_result [read $f]
close $f
puts $fault_result
if {![string match {*injected early request must FAIL*} $fault_result] || [string match {*ALL TESTS PASSED*} $fault_result] || [string match {*TIMEOUT*} $fault_result]} {error "Negative injection did not fail as expected"}
puts {=== EXPECTED EARLY-REQUEST FAULT DETECTED ===}
quit -code 0 -f

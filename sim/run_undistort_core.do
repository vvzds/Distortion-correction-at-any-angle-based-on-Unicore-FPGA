# 在 sim 目录执行：vsim -c -do run_undistort_core.do -l core_suite_transcript.log
# 任一编译、优化、结果缺失或自检失败均返回非零退出码。
onerror {quit -code 1 -f}
transcript on
if {![file exists work/_info]} {vlib work}
vlog -work work ../source/rtl/undistort_map.v ../source/rtl/undistort_line_cache.v ../source/rtl/undistort_bilinear.v ../source/rtl/undistort_core.v
vlog -work work undistort_core_sim_tb.v undistort_core_t1_tb.v undistort_core_t2_tb.v undistort_core_golden_tb.v
foreach name {sim t1 t2 golden} {
    vopt work.undistort_core_${name}_tb +acc -o core_${name}_suite
}
set summary [open core_suite_result.txt w]
proc check_result {path summary} {
    if {![file exists $path]} {error "Missing result: $path"}
    set f [open $path r]
    set result [read $f]
    close $f
    puts $result
    puts $summary $result
    flush $summary
    if {[regexp {FAIL|TIMEOUT} $result] ||
        [string trim [lindex [split [string trim $result] \n] end]] ne {=== ALL TESTS PASSED (err=0) ===}} {
        error "Self-check failed: $path"
    }
}
foreach name {sim t1 t2} {
    if {$name eq "t1"} {
        set result core_t1_final_result.txt
        file delete -force core_t1_result.txt
    } else {set result core_${name}_result.txt}
    file delete -force $result
    puts "RUN core_$name"
    vsim work.core_${name}_suite
    onfinish stop
    run -all
    quit -sim
    if {$name eq "t1"} {
        set f [open core_t1_result.txt r]
        set perframe [read $f]
        close $f
        puts $perframe
        puts $summary $perframe
        if {[regexp {FAIL|TIMEOUT} $perframe]} {error "T1 per-frame check failed"}
    }
    check_result $result $summary
}
foreach pair {{3 0} {4 0} {51 0} {52 0} {53 0} {6 0} {3 1} {4 1}} {
    set test [lindex $pair 0]
    set pattern [lindex $pair 1]
    set result core_${test}_p${pattern}_result.txt
    file delete -force $result
    puts "RUN TEST=$test PATTERN=$pattern"
    vsim work.core_golden_suite +TEST=$test +PATTERN=$pattern +RESULT=$result
    onfinish stop
    run -all
    quit -sim
    check_result $result $summary
}
puts {=== CORE SUITE PASSED: T0-T9 (err=0) ===}
puts $summary {=== CORE SUITE PASSED: T0-T9 (err=0) ===}
puts $summary {=== ALL TESTS PASSED (err=0) ===}
close $summary
quit -code 0 -f

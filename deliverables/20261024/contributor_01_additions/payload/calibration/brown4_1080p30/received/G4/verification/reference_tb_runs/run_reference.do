# 从 reference_tb_runs 执行；原件保留在 ../reference_package/01_ref。
onerror {quit -code 1 -f}
transcript on
if {![file exists work/_info]} {vlib work}
vlog -work work ../reference_package/01_ref/param_mgr.v param_mgr_tb.v
vlog -work work ../reference_package/01_ref/gamma_lut.v gamma_lut_tb.v
foreach mod {param_mgr gamma_lut} {
    vopt work.${mod}_tb +acc -o ${mod}_reference
    file delete -force ${mod}_result.txt
    vsim work.${mod}_reference
    onfinish stop
    run -all
    quit -sim
    if {![file exists ${mod}_result.txt]} {error "Missing result: $mod"}
    set f [open ${mod}_result.txt r]
    set result [read $f]
    close $f
    puts $result
    if {![string match {*ALL TESTS PASSED (err=0*} $result] ||
        [regexp {FAIL|TIMEOUT} $result]} {error "Reference self-check failed: $mod"}
}
quit -code 0 -f

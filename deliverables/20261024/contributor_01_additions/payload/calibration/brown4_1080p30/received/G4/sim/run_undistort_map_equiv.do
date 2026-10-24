# 在sim目录运行；使用独立库，不干扰正在进行的core suite。
onerror {quit -code 1 -f}
if {![file exists equiv_work/_info]} {vlib equiv_work}
vlog -work equiv_work ../verification/g1_baseline/undistort_map_v12_ref.v ../source/rtl/undistort_map.v undistort_map_equiv_tb.v
vopt -work equiv_work equiv_work.undistort_map_equiv_tb +acc -o map_equiv_acc
file delete -force map_equiv_result.txt
vsim equiv_work.map_equiv_acc
onfinish stop
run -all
quit -sim
if {![file exists map_equiv_result.txt]} {error "Missing equivalence result"}
set f [open map_equiv_result.txt r]
set result [read $f]
close $f
puts $result
if {[regexp {FAIL|TIMEOUT} $result] || ![string match {*ALL TESTS PASSED (err=0)*} $result]} {error "Equivalence failed"}
quit -code 0 -f

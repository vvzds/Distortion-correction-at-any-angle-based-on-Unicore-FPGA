onerror {quit -code 1 -f}
transcript on
vlib work
vlog +define+AB_CANDIDATE ../rtl/*.v source/rtl/corr_subsys/rect_wr_if.v source/rtl/corr_write_pack.v source/rtl/corr_write_arb.v source/rtl/corr_read_bridge.v core30_system_tb.v
vopt work.core30_system_tb +acc -o test_opt
vsim work.test_opt +TEST=10 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=16 +RESULT=real_result.txt
onfinish stop
run -all
quit -sim
set f [open real_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=21 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=16 +RESULT=rotate5_result.txt
onfinish stop
run -all
quit -sim
set f [open rotate5_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
quit -code 0 -f

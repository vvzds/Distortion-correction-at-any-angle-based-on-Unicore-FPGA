onerror {quit -code 1 -f}
transcript on
vlib work
vlog +define+AB_CANDIDATE ../../rtl/*.v source/rtl/corr_subsys/rect_wr_if.v source/rtl/corr_write_pack.v source/rtl/corr_write_arb.v source/rtl/corr_read_bridge.v core30_system_tb.v
vopt work.core30_system_tb +acc -o test_opt
vsim work.test_opt +TEST=0 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=1 +RESULT=identity_result.txt
onfinish stop
run -all
quit -sim
set f [open identity_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=10 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=1 +RESULT=real_full_result.txt
onfinish stop
run -all
quit -sim
set f [open real_full_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=11 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=16 +RESULT=affine_plus_result.txt
onfinish stop
run -all
quit -sim
set f [open affine_plus_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=12 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=16 +RESULT=affine_minus_result.txt
onfinish stop
run -all
quit -sim
set f [open affine_minus_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=6 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=16 +RESULT=offcenter_result.txt
onfinish stop
run -all
quit -sim
set f [open offcenter_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=3 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=16 +RESULT=negative_radial_result.txt
onfinish stop
run -all
quit -sim
set f [open negative_radial_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=4 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=16 +RESULT=tangential_result.txt
onfinish stop
run -all
quit -sim
set f [open tangential_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=51 +PATTERN=1 +DDR_WAIT=0 +GRANT_WAIT=0 +DDR_GAP=0 +STRIDE=16 +RESULT=clamp_plus_result.txt
onfinish stop
run -all
quit -sim
set f [open clamp_plus_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=52 +PATTERN=1 +DDR_WAIT=0 +GRANT_WAIT=0 +DDR_GAP=0 +STRIDE=16 +RESULT=clamp_minus_result.txt
onfinish stop
run -all
quit -sim
set f [open clamp_minus_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=53 +PATTERN=1 +DDR_WAIT=0 +GRANT_WAIT=0 +DDR_GAP=0 +STRIDE=16 +RESULT=clamp_fraction_result.txt
onfinish stop
run -all
quit -sim
set f [open clamp_fraction_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
vsim work.test_opt +TEST=20 +PATTERN=1 +DDR_WAIT=64 +GRANT_WAIT=16 +DDR_GAP=3 +STRIDE=16 +RESULT=rotate1_result.txt
onfinish stop
run -all
quit -sim
set f [open rotate1_result.txt r]
set r [read $f]
close $f
puts $r
if {[string first {=== ALL TESTS PASSED (err=0) ===} $r]<0} {quit -code 2 -f}
quit -code 0 -f

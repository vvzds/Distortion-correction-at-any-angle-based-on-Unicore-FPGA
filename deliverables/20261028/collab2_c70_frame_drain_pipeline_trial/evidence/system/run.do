onerror {quit -code 1 -f}
vlib work
vlog +define+AB_CANDIDATE ../../rtl/*.v source/rtl/corr_subsys/rect_wr_if.v source/rtl/corr_write_pack.v source/rtl/corr_write_arb.v source/rtl/corr_read_bridge.v core30_system_tb.v
vopt work.core30_system_tb +acc -o test_opt

foreach {test name ddr_wait grant_wait ddr_gap stride} {
    23 rotate90 64 16 3 16
} {
    vsim work.test_opt +TEST=$test +PATTERN=1 +DDR_WAIT=$ddr_wait +GRANT_WAIT=$grant_wait +DDR_GAP=$ddr_gap +STRIDE=$stride +RESULT=c70_${name}_result.txt
    onfinish stop
    run -all
    quit -sim
    set f [open c70_${name}_result.txt r]
    set result [read $f]
    close $f
    if {[string first {=== ALL TESTS PASSED (err=0) ===} $result] < 0} {quit -code 2 -f}
}
quit -code 0 -f

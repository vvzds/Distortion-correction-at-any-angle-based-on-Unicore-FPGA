onerror {quit -code 1 -f}
vlib work
vlog rtl/strip_reorder.v strip_reorder_tb.v strip_reorder_rate_tb.v

foreach {name width height strip} {
    small_odd 7 5 2
    small_even 8 6 3
    wide_tail 1920 33 16
    full_1080p 1920 1080 16
} {
    vopt work.strip_reorder_tb -GWIDTH=$width -GHEIGHT=$height -GSTRIP_H=$strip +acc -o $name
    vsim work.$name
    onfinish stop
    run -all
    quit -sim
}

vopt work.strip_reorder_rate_tb +acc -o rate_opt
vsim work.rate_opt
onfinish stop
run -all
quit -sim
quit -code 0 -f

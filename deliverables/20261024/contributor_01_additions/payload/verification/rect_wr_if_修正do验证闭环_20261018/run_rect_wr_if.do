# ModelSim: run from the project root: vsim -c -do sim/run_rect_wr_if.do
# Or set rect_wr_if_root to an absolute project path before sourcing this file.
# ModelSim 10.7 may return an empty [info script] under -do.
onerror {quit -force -code 1}
if {[info exists rect_wr_if_root]} {
    set root [file normalize $rect_wr_if_root]
} else {
    set root [file normalize [pwd]]
}
set script_dir [file join $root sim]
foreach required [list [file join $root source rtl rect_wr_if.v] [file join $script_dir rect_wr_if_tb.v]] {
    if {![file isfile $required]} {
        puts "FAIL ModelSim: missing $required; run from project root or set rect_wr_if_root"
        quit -force -code 1
    }
}
set results [file join $root verification modelsim]
file mkdir $results
cd $results
transcript file [file join $results W0_W8_vsim.log]
transcript on
if {[file exists work]} {vdel -lib work -all}
vlib work
vmap work work
vlog -work work +define+SIMULATION [file join $root source rtl rect_wr_if.v] [file join $script_dir rect_wr_if_tb.v]
vsim -t 1ps -voptargs=+acc -onfinish stop work.rect_wr_if_tb
run -all
set failures [examine -radix decimal /rect_wr_if_tb/err]
set completed_normally [examine -radix unsigned /rect_wr_if_tb/tb_done]
set completed [examine -radix decimal /rect_wr_if_tb/commits]
if {$failures != 0 || $completed != 4 || $completed_normally != 1} {
    puts "FAIL ModelSim: err=$failures final_commits=$completed"
    quit -force -code 1
}
quit -force -code 0

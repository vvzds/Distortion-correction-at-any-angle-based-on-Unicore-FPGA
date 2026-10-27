onerror {quit -code 1 -f}
vlib work
vlog undistort_map.v undistort_map_tb.v
vopt work.undistort_map_tb +acc -o map_opt
vsim work.map_opt
onfinish stop
run -all
quit -code 0 -f

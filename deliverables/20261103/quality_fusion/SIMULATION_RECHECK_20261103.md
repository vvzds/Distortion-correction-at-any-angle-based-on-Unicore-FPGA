# Simulation Recheck: 2026-11-03

## Result

The final candidate is **not yet proven to sustain 30 distinct corrected frames
per second by functional simulation**. The installed ModelSim `vlog` compiler
compiled the final correction stress testbench, denoiser testbench, and sharpener
testbench with zero errors and zero warnings. ModelSim `vsim` then stopped before
running any testbench because its Tcl startup failed with
`can't read "FileWatch(fileName)": no such element in array`.

The compiler and simulator logs are retained beside this report. Changing to an
ASCII-only staging path avoided the Windows username encoding failure seen on
the first attempt, but did not fix the simulator startup failure.

## Timing Context

The final seed7 PDS timing report gives `pix_clk` as 74.2501 MHz. The raster
contract is 2200 clocks per line by 1125 lines per frame, which corresponds to
30.00004 HDMI refreshes per second. This confirms the configured HDMI scan rate,
not that every refresh contains a new corrected source frame.

The native frame testbench uses a 125 MHz processing clock and a 4,166,666-cycle
budget for a 30 fps correction frame. Existing native simulation artifacts were
checked against the current project source hashes; several source files differ,
so their reported frame throughput is not treated as evidence for this final
candidate.

## Acceptance Boundary

- PDS seed7 place/route and constrained timing: passed.
- Final RTL testbench compilation: passed with zero errors and zero warnings.
- Final functional simulation: blocked before test execution by ModelSim Tcl
  startup; no simulation PASS was produced.
- Stable 30 unique corrected frames/s and board display: not established.

Next verification requires repairing or replacing the local ModelSim runtime,
then running at least a long multi-frame correction/display stress test with
unique frame identifiers and frame-drop checks. Board validation remains
necessary for the actual camera-to-HDMI path.

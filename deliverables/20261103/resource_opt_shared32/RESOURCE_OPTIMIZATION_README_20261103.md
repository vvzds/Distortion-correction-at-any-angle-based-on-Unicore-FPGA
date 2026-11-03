# Shared-Multiplier Resource-Optimized Candidate

This is the complete portable PDS project for the function-key quality
pipeline, with the control-rate IMU matrix multiplier reduced from twelve
parallel instances to one pipelined II=1 instance. The seed-2 image is the
recommended first board-test image; seed 1 is retained as a fallback.

Read `RESOURCE_OPTIMIZATION_REPORT_20261103.md` first. The project source is
under `source/`, IP inputs under `ipcore/`, and the two images are under
`bitstreams/`. PDS timing and device-map evidence is under `pds_evidence/`.

The existing key behavior, denoise, sharpen, adaptive Gamma, OSD, host
protocol, calibration, and affine/IMU interfaces are retained. The optimizer
does not alter the per-pixel tile engine or frame/DDR ownership path.

Board procedure and power-on/runtime caveats remain in `BOARD_TEST.md` and
`KEY_FUNCTIONS_20261103.md`. The package has not been physically tested in
this pass.

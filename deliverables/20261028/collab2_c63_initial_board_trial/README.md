# C63 seed7 initial board trial package (2026-10-28)

## Status

This is a routed, bitstream-generated candidate for initial hardware inspection. It has not been programmed or board-tested. Keep the known board-tested C50 seed7 image as the fallback; this package does not replace or remove it.

The implementation uses the existing row-major camera capture and frame-buffer path. C63 registers frame-start acceptance and parameter qualification. Full-frame simulation passed 11 system scenarios and the 125 MHz PDS route closed. The 15-degree full-frame simulation timed out at 1,673,417 of 2,073,600 output pixels, so do not use this candidate to claim arbitrary-angle real-time operation. Begin with identity and the known small-angle configuration, then inspect output, DDR stability, and UART parameter loading.

## Bitstream identity

- File: `hdmi_ddr_ov5640_top_C63_seed7.sbit`
- SHA256: `A3FDEDA15E3538FA23B3E188608C79592B1816E558EF66403BC8321D64A58943`
- Target: PG2L100H-6 FBG676
- PDS: 2022.2-SP6.1
- Build: complete compile, synthesis, device map, route, post-route timing, and bitstream generation in the isolated C63 project
- Routed device usage: 112 APM, 29.5 DRM, 21,386 LUT, 25,807 FF
- Slow-corner 125 MHz DDR clock: setup WNS `+0.521 ns`, hold WHS `+0.083 ns`, zero failing endpoints; design summary says `All Constraints Met`
- Place-and-route log reports successful routing, zero remaining hold violations, and 184 detailed-route iterations
- The frame-buffer IP still emits the existing FBG484-versus-FBG676 metadata warning; verify actual board initialization during testing

The ZIP beside this folder contains the complete portable PDS source and IP project under `project/`, including the final bitstream and raw PDS build logs. This folder carries the bitstream separately for convenient programming, plus the test SOP and simulation evidence. The regenerated final route report is archived in the project; its slow-corner DDR WNS/WHS are +0.521/+0.083 ns. The earlier archived C63 experiment report (+0.445/+0.064 ns) is a different run and is not the report for this bitstream.

## Initial board test

Follow `06_initial_board_test_SOP.md`. Programming is intentionally a user-run board step. No board or flash was modified during this build. Keep the C50 image and original C50 package available for rollback.

## Next engineering gate

After initial board checks pass, continue the high-order task 2 work on source-read locality and cache scheduling. The C63 result is an initial board-test point, not task acceptance: the 15-degree stress case is still below the real-time target, and distinct camera-input/display FPS remains unmeasured.

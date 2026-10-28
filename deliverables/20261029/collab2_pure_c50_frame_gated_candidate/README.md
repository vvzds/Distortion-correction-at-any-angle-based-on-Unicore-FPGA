# Pure RAW8 capture + C50 correction, frame-gated candidate

Status: simulation and initial independent post-route timing passed. The
matched bitstream rebuild is in progress. No corrected 30-distinct-frame/s
board claim is made, and no board or Flash was changed.

## Integration

The project starts with the C50 correction host and replaces six acquisition
and display RTL files byte-for-byte from the AF961A pure 30 fps project:
`raw8_to_rgb565.v`, `wr_buf.v`, `rd_buf.v`, `sync_vg.v`, `reg_config.v`, and
`i2c_com.v`. The C50 raw-slot protection, corrected-slot controller, DDR
arbiters, UART, and correction writer remain. The tested C63 frame-start and
cache improvements replace only `undistort_core.v` and
`undistort_cache_ab.v`; both were rechecked against the simulation copies by
SHA256. `corr_top.v` now coalesces new raw-frame completion events and starts
at most one correction for each unconsumed source frame. A simultaneous new
event on the launch edge remains pending. Four diagnostic counters are read
through successive UART `0x05` requests: camera VSYNC, completed raw frames,
corrected publications, and actual HDMI slot advances.

## Verification

- ModelSim frame-gate test: five expected starts, five observed, zero errors;
  includes no-source idle, busy-time coalescing, invalid parameters, and the
  launch-edge race.
- ModelSim full 1920x1080 regression: 11/11 pixel-accuracy and protocol cases
  passed using the C63 core/cache hashes in this project. The synthetic DDR
  model includes concurrent 30 fps-equivalent capture writes and display
  reads. Corrected-frame publication: identity 44.330045 fps, calibrated
  parameters 37.491872 fps, 1-degree rotation 36.762576 fps. These are model
  publication rates, not independent camera or HDMI frame rates.
- PDS 2022.2-SP6.1, PG2L100H-6 FBG676, seed7: complete route and independent
  `report_timing` report `All Constraints Met`. At 125 MHz DDR, slow-corner
  setup WNS +0.324 ns; minimum hold WHS across corners +0.102 ns; zero failing
  endpoints. Device map: 21,393/66,600 LUT, 25,864/133,200 FF, 112/240 APM,
  29.5/155 DRM. The project retains the existing frame-buffer IP metadata
  warning (FBG484 versus FBG676); the actual target is FBG676.
- The direct C50-core fusion used 21,984 LUT and 26,053 FF but its independent
  setup WNS was -0.117 ns. It is rejected for a bitstream. Original C50 seed7
  remains the board-tested fallback and is not overwritten.

## Archive

- `project_sources.zip`: complete source/IP, constraints, build scripts,
  simulation testbenches, and four-stage UART probe. SHA256
  `21DAA2BE656AE1745C6DDE983445B2514156925813D844B3397EA4B2AE3B3268`.
- `seed7_route_evidence.zip`: raw PDS build log, timing summary, and independent
  routed timing report. SHA256
  `D92E393D852216EDC954C9A096F87B0545ACA2977AC34D9C16ADF8BD873E9298`.
- `evidence/fullframe/`: all 11 simulator result files; the frame-gate log is
  in `evidence/frame_gate_result.log`.

The next gate is a bitstream generated in the same PDS process as the routed
design, with fresh timing and SHA256. Later board validation must use the
camera/raw/publication/display counters plus a moving-scene HDMI frame-hash
window to demonstrate at least 30 distinct corrected images per second.

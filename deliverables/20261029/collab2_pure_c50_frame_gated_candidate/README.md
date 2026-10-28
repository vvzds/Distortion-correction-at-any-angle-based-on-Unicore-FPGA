# Pure RAW8 capture + C50 correction, frame-gated candidate

Status: simulation and final independent post-route timing passed. The
matching SRAM bitstream is archived. No corrected 30-distinct-frame/s board
claim is made, and no board or Flash was changed.

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
- ModelSim four-stage status-page test passed; the existing UART parameter
  manager regression completed with zero errors. The Python probe parser's
  valid-page and old-bitstream rejection tests also passed.
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
- The bitstream was generated after route and timing in the same PDS process.
  The final rerun reproduced the resource and timing numbers above. The
  standalone `gen_bit_stream` attempt failed with `Flow-0044` and produced no
  bitstream; its output is not used.
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
- `evidence/fullframe/`: all 11 simulator result files. The frame-gate,
  four-stage counter, and UART parameter regression logs are beside it.
- `C50_pure_capture_C63_frame_gate_seed7.sbit`: final SRAM bitstream,
  3,791,112 bytes, SHA256
  `069737CD5B58F2D583C424AA45C13B8AE108DE55C7FCD23264FA99933F4FD2B9`.
- `complete_PDS_project.zip`: full source/IP, PDS project file, constraints,
  scripts, tests, final bitstream, and final timing reports. SHA256
  `5A75F1F513A902824EEC5B530E492499CD822E6853AD388A4D93EC246E29CD3F`.
  The bitstream inside has the same SHA256 as the separate file.
- `final_bitstream_route_evidence.zip`: matched final PDS console log and
  independent timing reports. SHA256
  `6A2E57047CE02140D15287ED716CA5878CEF7E65C68C69EDB348CC061E41B730`.
- `rejected_C50_core_evidence.zip`: raw reports for the direct C50-core fusion
  that failed setup timing. SHA256
  `CBF3DD75F0332AAD2C6D2EB5DA1C136503270294B4C493D57E33FA2419879F14`.
- `parameters/real_parameters.csv`: the measured calibration used in the
  earlier board test; resend after SRAM download.

The remaining gate is real board validation. It must use the
camera/raw/publication/display counters plus a moving-scene HDMI frame-hash
window to demonstrate at least 30 distinct corrected images per second. See
`BOARD_VALIDATION.md` for the later SRAM-only test sequence.
